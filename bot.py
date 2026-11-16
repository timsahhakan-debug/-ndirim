"""
Hepsiburada İndirim Botu
Seçili kategorileri tarar, %30 ve üzeri indirimli ürünleri Telegram'a gönderir.
"""

import asyncio
import html
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import requests
from playwright.async_api import async_playwright

# ======================= AYARLAR =======================

# Her kategorinin linkini Hepsiburada'da o kategoriye girip
# tarayıcının adres çubuğundan kopyalayarak buraya yapıştır.
# Örnek görünüm: https://www.hepsiburada.com/xxxxx-c-123456
CATEGORIES = {
    "Bilgisayar": "https://www.hepsiburada.com/bilgisayar-sistemleri-ve-ekipmanlari-c-2147483646",
    "Süpermarket": "https://www.hepsiburada.com/supermarket-c-2147483619",
    "Kozmetik": "https://www.hepsiburada.com/kozmetik-c-2147483603",
    "Kişisel Bakım": "https://www.hepsiburada.com/saglik-kisisel-bakim-urunleri-c-2147483633",
    "Yapı Market": "https://www.hepsiburada.com/yapi-market-hirdavatlar-c-2147483620",
    "Oto Aksesuar": "https://www.hepsiburada.com/oto-aksesuarlari-c-2147483631",
}

MIN_DISCOUNT = 30          # yüzde olarak minimum indirim
PAGES_PER_CATEGORY = 3     # her kategoride kaç sayfa taranacak
TESHIS_MODU = False        # True iken ürün göndermez, örnek kutuların içeriğini gönderir
MAX_MESSAGES_PER_RUN = 40  # bir çalışmada en fazla kaç ürün gönderilecek
RESEND_AFTER_DAYS = 7      # aynı ürün kaç gün sonra tekrar gönderilebilir

# =======================================================

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DRY_RUN = os.environ.get("DRY_RUN") == "1"  # 1 ise Telegram'a göndermez, ekrana yazar
STATE_FILE = Path(__file__).parent / "sent.json"
DEBUG_DIR = Path(__file__).parent / "debug"
DIAG = []  # teşhis bilgileri

PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)\s*TL")
BADGE_RE = re.compile(r"%\s?(\d{1,2})\b")
# Fiyat sanılmaması gereken satırlar (taksit, kargo limiti, kupon vb.)
NOISE_WORDS = ("taksit", "kargo", "üzeri", "puan", "kupon", "hediye", "aylık")
INSTALLMENT_RE = re.compile(r"\d+\s*[xX×]\s*\d")


def parse_price(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def fmt_price(v: float) -> str:
    s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s[:-3] if s.endswith(",00") else s


def drop_installments(prices):
    """Başka bir fiyatın 3-12'ye bölümüne denk gelen tutarları (taksit) çıkarır."""
    out = []
    for p in prices:
        is_inst = any(
            q > p and abs(q / n - p) / p < 0.015
            for q in prices for n in range(3, 13)
        )
        if not is_inst:
            out.append(p)
    return out


def first_price(s: str):
    s = re.sub(r"\s+(?=[,.]\d)", "", s or "")
    m = PRICE_RE.search(s)
    return parse_price(m.group(1)) if m else None


def analyze_fields(c):
    """Hepsiburada'nın etiketli fiyat alanlarından indirim hesaplar."""
    old = first_price(c.get("orig"))
    new = first_price(c.get("fin"))
    m = re.search(r"(\d{1,2})", c.get("rate") or "")
    rate = float(m.group(1)) if m else 0.0
    if not old:          # eski fiyat yoksa indirim yok
        return None, new, 0.0
    calc = (old - new) / old * 100 if new and new < old else 0.0
    if calc and rate:
        disc = calc if abs(calc - rate) <= 3 else min(calc, rate)
    else:
        disc = calc or rate
    return old, new, disc


def analyze_card(text: str):
    """Kart metninden eski fiyat, yeni fiyat ve indirim oranını çıkarır."""
    prices = []
    for line in text.splitlines():
        low = line.lower()
        if "tl" not in low:
            continue
        if any(w in low for w in NOISE_WORDS) or INSTALLMENT_RE.search(line):
            continue
        prices += [parse_price(m) for m in PRICE_RE.findall(line)]
    prices = [p for p in prices if p > 0]
    prices = drop_installments(prices)

    old = new = None
    discount = 0.0
    if len(prices) >= 2:
        old, new = max(prices), min(prices)
        if old > 0 and old / new < 20:  # saçma oranları ele
            discount = (old - new) / old * 100

    if discount == 0:
        badges = [int(b) for b in BADGE_RE.findall(text)]
        if badges:
            discount = float(max(badges))
            if prices:
                new = min(prices)

    return old, new, discount


EXTRACT_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  const isProduct = h => /-p(m)?-[A-Za-z0-9]+/.test(h);
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.href.split('?')[0].split('#')[0];
    if (!isProduct(href) || seen.has(href)) continue;
    let el = a.closest('li, article') || a;
    let i = 0;
    while (el && !/TL/.test(el.innerText || '') && i < 6) { el = el.parentElement; i++; }
    if (!el) continue;
    const others = new Set([...el.querySelectorAll('a[href]')]
      .map(x => x.href.split('?')[0].split('#')[0]).filter(isProduct));
    if (others.size > 1) continue;  // birden fazla ürün içeren kutuları atla
    seen.add(href);
    const title = (a.getAttribute('title') || el.querySelector('h2, h3')?.innerText
                   || a.innerText.split('\n')[0] || '').trim();
    const bits = [];
    for (const x of el.querySelectorAll('*')) {
      if (x.children.length) continue;
      const tx = (x.innerText || '').trim();
      if (!/TL|%/.test(tx) || tx.length > 60) continue;
      const key = x.getAttribute('data-test-id') || (x.className && x.className.toString().slice(0, 40)) || x.tagName;
      bits.push(key + ' = ' + tx);
      if (bits.length >= 12) break;
    }
    const q = s => el.querySelector(s);
    const orig = q('[class*="originalPrice"]')?.innerText || '';
    const rate = q('[class*="discountRate"]')?.innerText || '';
    const frac = q('[class*="finalPriceFraction"]');
    const fin = q('[class*="finalPrice"]:not([class*="Fraction"])')?.innerText
                || frac?.parentElement?.innerText || '';
    const sepet = /Sepete özel/i.test(el.innerText || '');
    out.push({ url: href, title, text: el.innerText || '', bits, orig, rate, fin, sepet });
  }
  return out;
}
"""


def page_url(base: str, n: int) -> str:
    if n == 1:
        return base
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}sayfa={n}"


async def scrape_category(page, name, base_url):
    results, seen_count = [], 0
    for n in range(1, PAGES_PER_CATEGORY + 1):
        url = page_url(base_url, n)
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            status = resp.status if resp else "?"
            try:
                await page.wait_for_selector("a[href*='-p-'], a[href*='-pm-']", timeout=15000)
            except Exception:
                pass
            for _ in range(6):  # tembel yüklenen ürünler için aşağı kaydır
                await page.mouse.wheel(0, 2500)
                await page.wait_for_timeout(700)
            cards = await page.evaluate(EXTRACT_JS)
        except Exception as e:
            print(f"[{name}] sayfa {n} hata: {e}")
            DIAG.append(f"{name}: hata - {str(e)[:120]}")
            break

        print(f"[{name}] sayfa {n}: {len(cards)} ürün bulundu")
        seen_count += len(cards)
        if not cards:
            try:
                title = (await page.title())[:80]
                body = (await page.inner_text("body"))[:150].replace("\n", " ")
                DEBUG_DIR.mkdir(exist_ok=True)
                safe = re.sub(r"[^A-Za-z0-9]", "_", name)
                await page.screenshot(path=str(DEBUG_DIR / f"{safe}.png"), full_page=False)
                (DEBUG_DIR / f"{safe}.html").write_text(await page.content(), encoding="utf-8")
            except Exception as e:
                title, body = "?", str(e)[:100]
            print(f"[{name}] HTTP {status} | başlık: {title} | metin: {body}")
            DIAG.append(f"{name}: HTTP {status} | {title} | {body}")
            break
        for c in cards:
            old, new, disc = analyze_fields(c)
            if disc >= MIN_DISCOUNT and disc < 95:
                results.append({"url": c["url"], "title": c["title"], "sepet": c.get("sepet"),
                                "old": old, "new": new, "disc": disc, "cat": name, "text": c["text"],
                                "bits": c.get("bits", [])})
        await page.wait_for_timeout(random.randint(3000, 6000))  # siteyi yormamak için
    return results, seen_count


def send_telegram(text: str):
    if DRY_RUN:
        print("---\n" + text)
        return True
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": False},
        timeout=20,
    )
    if r.status_code == 429:  # hız sınırı
        time.sleep(r.json().get("parameters", {}).get("retry_after", 5) + 1)
        return send_telegram(text)
    if not r.ok:
        print("Telegram hatası:", r.text)
    return r.ok


def format_message(p) -> str:
    title = html.escape(p["title"][:150] or "Ürün")
    lines = [f"🔥 <b>%{p['disc']:.0f} indirim</b> · {html.escape(p['cat'])}", f"<b>{title}</b>"]
    if p["old"] and p["new"]:
        lines.append(f"<s>{fmt_price(p['old'])} TL</s> → <b>{fmt_price(p['new'])} TL</b>"
                     + (" (sepette)" if p.get("sepet") else ""))
    elif p["new"]:
        lines.append(f"<b>{fmt_price(p['new'])} TL</b>")
    lines.append(p["url"])
    return "\n".join(lines)


def load_state():
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    cutoff = time.time() - RESEND_AFTER_DAYS * 86400
    return {k: v for k, v in data.items() if v > cutoff}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=0), encoding="utf-8")


async def main():
    if not DRY_RUN and (not TOKEN or not CHAT_ID):
        sys.exit("TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID tanımlı değil.")

    if "--test-telegram" in sys.argv:
        ok = send_telegram("✅ Bot bağlantısı çalışıyor!")
        sys.exit(0 if ok else 1)

    cats = {k: v for k, v in CATEGORIES.items() if v.startswith("http")}
    if not cats:
        sys.exit("bot.py içindeki CATEGORIES listesine kategori linklerini yapıştırmalısın.")

    state = load_state()
    found, total_seen = [], 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True, channel="chromium",
            args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(
            locale="tr-TR", timezone_id="Europe/Istanbul",
            viewport={"width": 1366, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await ctx.new_page()
        for name, url in cats.items():
            items, count = await scrape_category(page, name, url)
            total_seen += count
            found += items
        await browser.close()

    if TESHIS_MODU:
        print(f"Teşhis modu: {len(found)} ürün indirimli sanıldı.")
        send_telegram(f"🔧 Teşhis modu: {total_seen} ürün okundu, {len(found)} tanesi indirimli sanıldı. Örnekler:")
        for p in sorted(found, key=lambda p: p["disc"], reverse=True)[:4]:
            msg = (f"%{p['disc']:.0f} sanıldı · {p['cat']}\n{p['url']}\n\nKUTU METNİ:\n{p['text'][:900]}"
                   f"\n\nFİYAT ALANLARI:\n" + "\n".join(p.get("bits", [])))
            send_telegram(html.escape(msg[:3800]))
            time.sleep(1.2)
        return

    # Aynı ürünü tekrar gönderme, en yüksek indirimden başla
    unique = {}
    for p in found:
        if p["url"] not in state and p["url"] not in unique:
            unique[p["url"]] = p
    to_send = sorted(unique.values(), key=lambda p: p["disc"], reverse=True)

    print(f"Toplam {len(found)} uygun ürün, {len(to_send)} yeni.")
    if total_seen == 0:
        detail = "\n\n".join(html.escape(d) for d in DIAG[:6])
        send_telegram("⚠️ Hiç ürün okunamadı. Teşhis:\n\n" + detail)

    sent = 0
    for p in to_send[:MAX_MESSAGES_PER_RUN]:
        if send_telegram(format_message(p)):
            state[p["url"]] = time.time()
            sent += 1
        time.sleep(1.2)

    if len(to_send) > MAX_MESSAGES_PER_RUN:
        send_telegram(f"ℹ️ {len(to_send) - MAX_MESSAGES_PER_RUN} indirimli ürün daha var, "
                      f"sonraki çalışmada gönderilecek.")

    save_state(state)
    print(f"{sent} mesaj gönderildi.")


if __name__ == "__main__":
    asyncio.run(main())
