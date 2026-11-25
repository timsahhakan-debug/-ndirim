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
    "Deterjan & Temizlik": "https://www.hepsiburada.com/deterjan-temizlik-urunleri-c-28001525",
    "Bebek Bezi": "https://www.hepsiburada.com/bebek-bezi-c-60001048",
    "Kağıt Ürünleri": "https://www.hepsiburada.com/kagit-urunleri-c-28001547",
    "İçecek": "https://www.hepsiburada.com/icecek-urunleri-c-28001517",
    "Gıda": "https://www.hepsiburada.com/gida-urunleri-c-28001469",
    "Mutfak Sarf Malzemeleri": "https://www.hepsiburada.com/mutfak-sarf-malzemeleri-c-60001205",
    "Parfüm": "https://www.hepsiburada.com/parfumler-c-341406",
    "Cilt Bakım": "https://www.hepsiburada.com/cilt-bakim-urunleri-c-32000005",
    "Ağız Bakım": "https://www.hepsiburada.com/agiz-bakim-urunleri-c-26012110",
    "Erkek Tıraş": "https://www.hepsiburada.com/erkek-tiras-urunleri-c-26012116",
    "Duş Jeli": "https://www.hepsiburada.com/dus-jelleri-c-26012356",
    "Saç Bakım": "https://www.hepsiburada.com/sac-bakim-urunleri-c-26012111",
    "Epilasyon & Ağda": "https://www.hepsiburada.com/epilasyon-agda-c-80216049",
    "Deodorant": "https://www.hepsiburada.com/deodorantlar-c-26012112",
    "Telefon Aksesuarları": "https://www.hepsiburada.com/cep-telefonu-aksesuarlari-c-371967",
    "Bluetooth Kulaklık": "https://www.hepsiburada.com/bluetooth-kulakliklar-c-16218",
    "Powerbank": "https://www.hepsiburada.com/tasinabilir-pilli-sarj-cihazlari-c-60004584",
    "Akıllı Saat": "https://www.hepsiburada.com/akilli-saatler-c-60003676",
    "Şarj Cihazları": "https://www.hepsiburada.com/sarj-cihazlari-c-16113",
    "Telefon Kabloları": "https://www.hepsiburada.com/telefon-kablolari-c-29010123",
    "Taşınabilir Hoparlör": "https://www.hepsiburada.com/tasinabilir-hoparlorler-c-376097",
    "Robot Süpürge": "https://www.hepsiburada.com/robot-supurge-c-80160033",
    "Saç Şekillendirme": "https://www.hepsiburada.com/sac-sekillendirme-cihazlari-c-26012129",
    "Elektrikli Mutfak Aletleri": "https://www.hepsiburada.com/elektrikli-mutfak-aletleri-c-22001",
    "Mutfak Gereçleri": "https://www.hepsiburada.com/mutfak-gerecleri-c-22500",
    "Aydınlatma": "https://www.hepsiburada.com/elektrik-aydinlatma-urunleri-c-13003201",
    "Elektrikli Aletler": "https://www.hepsiburada.com/elektrikli-aletler-aksesuarlar-c-13003081",
    "Hırdavat": "https://www.hepsiburada.com/hirdavat-urunleri-c-13003347",
    "Elektrik Tesisat": "https://www.hepsiburada.com/elektrik-tesisat-malzemeleri-c-80571082",
    "Oto Aksesuar": "https://www.hepsiburada.com/oto-aksesuar-urunleri-c-253574",
    "Oto Ses & Görüntü": "https://www.hepsiburada.com/oto-ses-goruntu-sistemleri-c-253575",
    "Oto Yedek Parça": "https://www.hepsiburada.com/oto-yedek-parcalar-c-20003812",
    "Kadın Giyim": "https://www.hepsiburada.com/bayan-giyim-modelleri-c-12087178",
    "Erkek Giyim": "https://www.hepsiburada.com/erkek-giyim-modelleri-c-12087177",
    "Erkek Kol Saati": "https://www.hepsiburada.com/erkek-kol-saatleri-c-25008404",
    "Kadın Kol Saati": "https://www.hepsiburada.com/bayan-kol-saatleri-c-25008405",
}

MIN_DISCOUNT = 30          # yüzde olarak minimum indirim
PAGES_PER_CATEGORY = 3     # her kategoride kaç sayfa taranacak
# Hepsiburada alt kategorileri (daha az sayfa taranır)
HB_SUB_CATEGORIES = {}  # artık tüm kategoriler yukarıda
HB_SUB_PAGES = 2

TRENDYOL_CATEGORIES = {
    "Süpermarket": "https://www.trendyol.com/butik/liste/16/supermarket",
    "Kozmetik": "https://www.trendyol.com/butik/liste/11/kozmetik",
    "Ayakkabı & Çanta": "https://www.trendyol.com/butik/liste/9/ayakkabi-canta",
    "Elektronik": "https://www.trendyol.com/butik/liste/5/elektronik",
    "Kadın": "https://www.trendyol.com/butik/liste/1/kadin",
    "Erkek": "https://www.trendyol.com/butik/liste/2/erkek",
}
TRENDYOL_PAGES = 1         # Trendyol'da kategori başına sayfa
TRENDYOL_TESHIS = False    # True iken Trendyol ürünleri gönderilmez, örnek kutular gönderilir
N11_CATEGORIES = {
    "Ayakkabı & Çanta": "https://www.n11.com/ayakkabi-ve-canta",
    "Kadın Giyim": "https://www.n11.com/kadin-giyim-aksesuar",
    "Erkek Giyim": "https://www.n11.com/erkek-giyim-aksesuar",
    "Telefon & Aksesuar": "https://www.n11.com/telefon-ve-aksesuarlari",
    "Elektrikli Ev Aletleri": "https://www.n11.com/elektrikli-ev-aletleri",
    "Mutfak Gereçleri": "https://www.n11.com/mutfak-gerecleri",
    "Yapı Market & Bahçe": "https://www.n11.com/yapi-market-ve-bahce",
    "Gıda & Şekerleme": "https://www.n11.com/supermarket/gida-ve-sekerleme",
    "Deterjan & Temizlik": "https://www.n11.com/supermarket/deterjan-ve-temizlik",
    "Parfüm & Deodorant": "https://www.n11.com/parfum-ve-deodorant",
    "Saç Bakım": "https://www.n11.com/sac-bakim-ve-sekillendirme",
    "Yüz & Vücut Bakımı": "https://www.n11.com/yuz-ve-vucut-bakimi",
    "Makyaj": "https://www.n11.com/makyaj",
    "Sağlık & Medikal": "https://www.n11.com/saglik-ve-medikal-urunler",
    "Erkek Bakım": "https://www.n11.com/erkek-bakim-urunleri",
    "Kadın Bakım": "https://www.n11.com/kadin-bakim-urunleri",
    "Oto Aksesuar & Tuning": "https://www.n11.com/aksesuar-ve-tuning",
}
N11_PAGES = 1              # N11'de kategori başına sayfa
N11_TESHIS = False         # True iken N11 ürünleri gönderilmez, örnek kutular gönderilir

SITE_PAGES = {"Trendyol": TRENDYOL_PAGES, "N11": N11_PAGES}
SITE_TESHIS = {"Trendyol": TRENDYOL_TESHIS, "N11": N11_TESHIS}
SITE_PAGE_KEY = {"Hepsiburada": "sayfa", "Trendyol": "pi", "N11": "pg"}
AKAKCE_TESHIS = False      # eski teşhis (kapalı)
AKAKCE_FILTRE = True       # sadece Akakçe'ye göre son 6 ayın en düşük fiyatındaki ürünleri gönder
AKAKCE_MAX_KONTROL = 25    # her işte, her çalışmada Akakçe'de en fazla kaç ürün kontrol edilsin
AKAKCE_TOLERANS = 1.01     # fiyatımız Akakçe'deki en ucuzdan en fazla %1 yüksek olabilir
GECMIS_GUN = 183           # fiyat geçmişi ne kadar tutulsun (gün)
GECMIS_MIN_GUN = 30        # kendi geçmişimize güvenmek için gereken en az gün
SAMPLES = {}               # teşhis için örnek kutular
TESHIS_MODU = False        # True iken ürün göndermez, örnek kutuların içeriğini gönderir
MAX_MESSAGES_PER_RUN = 40  # bir çalışmada en fazla kaç ürün gönderilecek
RESEND_AFTER_DAYS = 7      # aynı ürün kaç gün sonra tekrar gönderilebilir

# =======================================================

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
# Birden fazla alıcı: virgülle ayır (örn. "2041320927,123456789,@kanaladi")
CHAT_IDS = [c.strip() for c in CHAT_ID.split(",") if c.strip()]
DRY_RUN = os.environ.get("DRY_RUN") == "1"  # 1 ise Telegram'a göndermez, ekrana yazar
# Paralel çalışma: her iş kendi sitesini/parçasını tarar ve kendi kaydını tutar
SITE = os.environ.get("SITE", "")            # "", "Hepsiburada", "Trendyol", "N11"
SHARD = os.environ.get("SHARD", "1/1")       # örn. "1/2"
JOB_KEY = os.environ.get("JOB_KEY", "")      # örn. "hb1"
_SUFFIX = f"_{JOB_KEY}" if JOB_KEY else ""
STATE_FILE = Path(__file__).parent / f"sent{_SUFFIX}.json"
LEGACY_STATE = Path(__file__).parent / "sent.json"
DEBUG_DIR = Path(__file__).parent / "debug"
STATUS_FILE = Path(__file__).parent / f"durum{_SUFFIX}.json"
HISTORY_FILE = Path(__file__).parent / "history" / f"fiyat{_SUFFIX}.json"  # GitHub önbelleğinde tutulur
PRICE_SEEN = {}            # bu çalışmada görülen tüm ürün fiyatları
AKAKCE_CACHE_FILE = Path(__file__).parent / f"akakce{_SUFFIX}.json"  # Akakçe sonuç önbelleği  # arka arkaya engellenme sayısı
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
  const isProduct = h => /-p(m)?-[A-Za-z0-9]+/.test(h) || /n11\.com\/urun\//.test(h);
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
    const badge = /en çok|satan|kargo|sepetinde|kaçırma|kupon|teslimat|tl\b|^\d|^\(|puan|indirim|fırsat|yeni/i;
    const lines = (a.innerText || el.innerText || '').split('\n').map(s => s.trim())
      .filter(s => s.length >= 12 && !badge.test(s));
    const title = (a.getAttribute('title') || el.querySelector('h2, h3')?.innerText
                   || lines[0] || a.innerText.split('\n')[0] || '').trim();
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
    const isN11 = location.hostname.includes('n11.com');
    const orig = (q('[class*="originalPrice"]') || q('[class*="current-price__old"]')
                  || (isN11 ? q('.price') : null))?.innerText || '';
    const rate = (q('[class*="discountRate"]') || q('[class*="price-discount-badge"]'))?.innerText || '';
    const frac = q('[class*="finalPriceFraction"]');
    const fin = q('[class*="finalPrice"]:not([class*="Fraction"])')?.innerText
                || frac?.parentElement?.innerText
                || q('[class*="current-price__current"]')?.innerText
                || (isN11 ? q('.price-currency')?.innerText : '') || '';
    const sepet = /Sepete özel|SEPETTE/i.test(el.innerText || '');
    out.push({ url: href, title, text: el.innerText || '', bits, orig, rate, fin, sepet });
  }
  return out;
}
"""


def page_url(base: str, n: int, site: str = "Hepsiburada") -> str:
    if n == 1:
        return base
    sep = "&" if "?" in base else "?"
    key = SITE_PAGE_KEY.get(site, "sayfa")
    return f"{base}{sep}{key}={n}"


async def trendyol_select_country(page):
    """Yurt dışı IP'lerde çıkan 'ülke seçin' penceresinde Türkiye'yi seçer."""
    try:  # pencere JavaScript ile birkaç saniye sonra açılıyor, bekle
        await page.wait_for_selector("text=/select your country/i", timeout=8000)
    except Exception:
        return  # pencere çıkmadı
    print("Trendyol ülke seçimi penceresi bulundu, Türkiye seçiliyor...")
    for loc in (page.get_by_text("Türkiye", exact=True), page.get_by_role("button", name="Türkiye"),
                page.locator("text=Türkiye")):
        try:
            await loc.first.click(timeout=5000)
            break
        except Exception:
            continue
    await page.wait_for_timeout(1500)
    for label in ("Select", "Seç", "Continue", "Devam", "Devam Et", "Alışverişe Başla", "Shop", "Confirm", "Onayla"):
        try:
            btn = page.get_by_role("button", name=label, exact=True)
            if await btn.count():
                await btn.first.click(timeout=3000)
                break
        except Exception:
            continue
    await page.wait_for_timeout(2000)
    try:
        await page.reload(wait_until="domcontentloaded", timeout=45000)
    except Exception:
        pass
    try:
        try:
            await page.wait_for_selector("text=/select your country/i", timeout=6000)
            still = True
        except Exception:
            still = False
        print("Ülke seçimi", "BAŞARISIZ" if still else "tamam")
        if still:
            buttons = await page.evaluate("""() => [...document.querySelectorAll('button, a, [role=button], li, label')]
                .filter(e => /türkiye|turkey|select|seç|continue|devam/i.test(e.innerText || ''))
                .slice(0, 8)
                .map(e => e.tagName + '.' + (e.className || '').toString().slice(0, 40) + ' = ' + (e.innerText || '').trim().slice(0, 40))""")
            DIAG.append("Trendyol: ülke seçimi geçilemedi. Butonlar: " + " | ".join(buttons))
    except Exception:
        pass


AKAKCE_JS = r"""
() => {
  const txt = document.body ? document.body.innerText : '';
  const lines = txt.split('\n').map(s => s.trim()).filter(Boolean);
  const hits = lines.filter(l => /düşük|geçmiş|grafik|son \d+ ay|aylık|fiyat değişim/i.test(l) && l.length < 120).slice(0, 15);
  const els = [...document.querySelectorAll('[id],[class]')]
    .map(e => (e.id ? '#' + e.id : '') + (e.className ? '.' + e.className.toString().split(' ')[0] : ''))
    .filter(s => /hist|chart|grafik|gecmis|price/i.test(s));
  const uniq = [...new Set(els)].slice(0, 15);
  const scripts = [...document.scripts].map(s => s.src || '').filter(s => /hist|chart|price/i.test(s)).slice(0, 5);
  return { hits, els: uniq, scripts };
}
"""


TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def norm_tokens(s: str):
    s = s.translate(TR_MAP).lower()
    s = re.sub(r"(\d)\s*(ml|gr|g|kg|lt|l|adet|kapsul|tablet|li|lu|x)\b", r"\1\2", s)
    return set(re.findall(r"[a-z0-9]+", s))


def match_score(ours: str, theirs: str) -> float:
    a, b = norm_tokens(ours), norm_tokens(theirs)
    if not a or not b:
        return 0.0
    unit = re.compile(r"^\d+(ml|gr|g|kg|lt|l|adet|kapsul|tablet|li|lu|x|cm|mm|mah|w|v|lt)$|^x\d+$")
    nums = {x for x in a if unit.match(x)}
    if nums and not nums <= b:          # ölçü sayıları (ml, adet, kapsül) tutmalı
        return 0.0
    a2 = {x for x in a if not re.fullmatch(r"\d{5,}", x)}   # uzun ürün kodlarını sayma
    b2 = {x for x in b if not re.fullmatch(r"\d{5,}", x)}
    return len(a2 & b2) / max(1, len(a2 | b2))


PERIOD_JS = r"""
() => [...document.querySelectorAll('button, a, li, span, label, div, option')]
  .filter(e => e.children.length === 0)
  .map(e => (e.innerText || '').trim())
  .filter(t => /^(\d+\s*(ay|yıl|gün)|son \d+ (ay|yıl)|tümü|tablo|grafik)$/i.test(t))
"""

TABLE_JS = r"""
() => {
  const rows = [...document.querySelectorAll('table tr')].map(r => r.innerText.replace(/\s+/g, ' ').trim()).filter(Boolean);
  const pt = document.querySelector('#priceTitle');
  const box = pt ? (pt.closest('section, div') || pt.parentElement) : null;
  const lines = (document.body.innerText || '').split('\n').map(s => s.trim())
    .filter(l => /en ucuz fiyat|daha düşük fiyat gördü|son \d+ (ay|yıl)/i.test(l) && l.length < 150);
  return { rows: rows.slice(0, 8), rowCount: rows.length, lastRows: rows.slice(-3),
           box: box ? box.innerText.slice(0, 500) : '', lines: [...new Set(lines)].slice(0, 6) };
}
"""


SECTION_JS = r"""
() => {
  const body = document.body ? document.body.innerText : '';
  if (!/fiyat değişim/i.test(body)) return null;
  // "Fiyat Değişimi" içeren en küçük anlamlı kutuyu bul
  let best = null;
  for (const e of document.querySelectorAll('section, div, article')) {
    const tx = e.innerText || '';
    if (/fiyat değişim/i.test(tx) && tx.length > 60 && (!best || tx.length < best.innerText.length)) best = e;
  }
  const clickables = best ? [...best.querySelectorAll('*')]
    .map(e => (e.innerText || '').trim()).filter(t => t && t.length < 15) : [];
  return { text: best ? best.innerText.slice(0, 700) : '', clickables: [...new Set(clickables)].slice(0, 20) };
}
"""


async def akakce_find(page, title):
    """Ürünü Akakçe'de arar, en iyi eşleşmenin linkini ve puanını döndürür."""
    from urllib.parse import quote
    q = " ".join(title.split()[:8])
    await page.goto(f"https://www.akakce.com/arama/?q={quote(q)}", wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(2500)
    links = await page.evaluate(r"""() => {
        const seen = new Set(); const res = [];
        for (const a of document.querySelectorAll('a[href]')) {
          const h = a.href.split('?')[0];
          if (!/akakce\.com\/.+,\d+\.html/.test(h) || seen.has(h)) continue;
          seen.add(h);
          const box = a.closest('li') || a;
          const t = (a.title || box.querySelector('h3, h2')?.innerText || a.innerText || '').split('\n')[0].trim();
          res.push({h, t: t.slice(0, 120)});
          if (res.length >= 10) break;
        }
        return res; }""")
    scored = sorted(((match_score(title, l["t"]), l) for l in links), key=lambda x: -x[0])
    return scored[0] if scored else (0.0, None)


async def akakce_probe(page, candidates):
    """Teşhis: fiyat geçmişi olan bir ürün bulana kadar adayları dener, geçmiş verisinin kaynağını kaydeder."""
    out = []
    seen_titles = set()
    tried = 0
    for p in candidates:
        title = p["title"]
        if title in seen_titles or tried >= 4:
            continue
        seen_titles.add(title)
        tried += 1
        try:
            sc, best = await akakce_find(page, title)
            if not best or sc < 0.45:
                out.append(f"✗ Eşleşme yok ({sc:.2f}): {title[:60]}")
                continue
            captured = []

            async def on_resp(r):
                u = r.url
                ct = r.headers.get("content-type", "")
                if "akakce" in u and ("json" in ct or re.search(r"price|fiyat|hist|gecmis|chart|grafik|graph", u, re.I)) \
                        and not re.search(r"\.(js|css|png|jpg|webp|svg|woff2?)(\?|$)", u):
                    try:
                        body = (await r.text())[:300]
                    except Exception:
                        body = "?"
                    captured.append(f"{r.status} {u[:130]}\n   {body}")

            page.on("response", on_resp)
            await page.goto(best["h"], wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(2500)
            for _ in range(12):
                await page.mouse.wheel(0, 1500)
                await page.wait_for_timeout(500)
            await page.wait_for_timeout(1500)
            sec = await page.evaluate(SECTION_JS)
            if not sec:
                page.remove_listener("response", on_resp)
                out.append(f"✗ Fiyat geçmişi bölümü yok ({sc:.2f}): {best['t'][:60]}")
                if captured:
                    out.append("  VERİ İSTEKLERİ:\n" + "\n".join(captured[:3]))
                continue
            out.append(f"✓ Geçmişi olan ürün ({sc:.2f}): {best['t'][:70]}\n{best['h'][:120]}")
            out.append("BUTONLAR: " + " | ".join(sec["clickables"]))
            try:
                await page.get_by_text("Tablo", exact=True).first.click(timeout=4000)
                await page.wait_for_timeout(2000)
                out.append("Tablo açıldı")
            except Exception:
                out.append("Tablo butonuna tıklanamadı")
            sec2 = await page.evaluate(SECTION_JS)
            out.append("BÖLÜM METNİ:\n" + (sec2 or sec)["text"])
            await page.wait_for_timeout(1500)
            page.remove_listener("response", on_resp)
            out.append("VERİ İSTEKLERİ:\n" + ("\n".join(captured[:5]) or "yok"))
            break
        except Exception as e:
            out.append(f"Hata: {str(e)[:120]}")
    return "\n".join(out)


LOWPRICE_JS = r"""
() => {
  // Sadece sayfanın ana ürününün (Product) fiyatını al; 0 ve geçersiz değerleri yok say
  const num = v => { const n = parseFloat(v); return isFinite(n) && n > 0 ? n : null; };
  const products = [];
  const walk = o => {
    if (!o || typeof o !== 'object') return;
    if (Array.isArray(o)) return o.forEach(walk);
    const tp = [].concat(o['@type'] || []);
    if (tp.includes('Product')) products.push(o);
    Object.values(o).forEach(walk);
  };
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    try { walk(JSON.parse(s.textContent)); } catch (e) {}
  }
  for (const p of products) {
    const offers = [].concat(p.offers || []);
    for (const of of offers) {
      const v = num(of.lowPrice) ?? num(of.price);
      if (v) return v;
    }
  }
  return null;
}
"""


async def akakce_check(page, p):
    """Ürünü Akakçe'de kontrol eder. Döner: (geçti_mi, sebep, akakçe_en_ucuz)"""
    sc, best = await akakce_find(page, p["title"])
    short = len(norm_tokens(p["title"])) <= 6        # kısa/genel başlıklar
    if not best or sc < (0.8 if short else 0.55):
        return False, "eşleşme yok" + (" (başlık çok genel)" if short and best and sc >= 0.55 else ""), None
    await page.goto(best["h"], wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(2000)
    for _ in range(12):
        await page.mouse.wheel(0, 1500)
        await page.wait_for_timeout(400)
    await page.wait_for_timeout(1000)
    low = await page.evaluate(LOWPRICE_JS)
    if not await page.evaluate(SECTION_JS):
        return False, "fiyat geçmişi yok", low
    sec = await page.evaluate(SECTION_JS) or {"text": ""}
    m = re.search(r"Bu (ürün|fiyat)[^\n.]*\.?", sec["text"] or "")
    txt = m.group(0) if m else ""
    if re.search(r"daha düşük fiyat gördü", txt, re.I):
        return False, "son 1 ayda daha düşük görmüş", low
    if not re.search(r"son 1 ay\w*\s+en ucuz", txt, re.I):
        return False, f"cümle okunamadı: {txt[:60] or '(yok)'}", low
    if low is None:
        return False, "Akakçe fiyatı okunamadı", low
    if p["new"] and p["new"] > low * AKAKCE_TOLERANS:
        return False, f"Akakçe'de daha ucuz", low
    return True, "1 ayın en düşüğü (Akakçe)", low


async def akakce_filter(page, cands, report):
    """Adayları Akakçe ile süzer; önbellek kullanır (24 saat)."""
    try:
        cache = json.loads(AKAKCE_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    now = time.time()
    cache = {k: v for k, v in cache.items() if now - v.get("t", 0) < 86400}
    passed, checked = [], 0
    for p in cands:
        key = p["url"]
        c = cache.get(key)
        if c and c.get("price") == p["new"]:
            ok, why, low = c["ok"], c["why"] + " (önbellek)", c.get("low")
        else:
            if checked >= AKAKCE_MAX_KONTROL:
                continue  # sonraki çalışmada kontrol edilir
            checked += 1
            try:
                ok, why, low = await akakce_check(page, p)
            except Exception as e:
                ok, why, low = False, f"hata: {str(e)[:60]}", None
            cache[key] = {"ok": ok, "why": why, "low": low, "price": p["new"], "t": now}
            await page.wait_for_timeout(random.randint(1500, 3000))
        report.append(f"{'✅' if ok else '✗'} {p['title'][:45]} | bizde {fmt_price(p['new'] or 0)} | "
                      f"Akakçe {fmt_price(low) if low else '-'} | {why}")
        if ok:
            p["akakce_low"] = low
            passed.append(p)
    AKAKCE_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return passed


def load_history():
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def history_info(hist, url, today):
    """Kayıtlardaki geçmiş: (kaç günlük, dönemdeki en düşük fiyat). Bugünkü kayıt hariç."""
    rows = [r for r in hist.get(url, []) if r[0] < today]
    if not rows:
        return 0, None
    cutoff = today - GECMIS_GUN
    window = [r for r in rows if r[0] >= cutoff]
    before = [r for r in rows if r[0] < cutoff]
    if before:                      # dönem başında geçerli olan fiyat
        window.append(before[-1])
    first_day = max(rows[0][0], cutoff)
    return today - first_day, min(r[1] for r in window)


def update_history(hist, today):
    """Bu çalışmada görülen fiyatları ekler (sadece değişince), eski kayıtları siler."""
    cutoff = today - GECMIS_GUN
    for url, price in PRICE_SEEN.items():
        rows = hist.setdefault(url, [])
        if rows and rows[-1][0] == today:
            rows[-1][1] = min(rows[-1][1], price)   # gün içindeki en düşük
        elif not rows or rows[-1][1] != price:
            rows.append([today, price])
    for url in list(hist):
        rows = hist[url]
        old = [r for r in rows if r[0] < cutoff]
        keep = ([old[-1]] if old else []) + [r for r in rows if r[0] >= cutoff]
        if not keep or keep[-1][0] < cutoff:       # 6 aydır görülmeyen ürün
            del hist[url]
        else:
            hist[url] = keep
    HISTORY_FILE.parent.mkdir(exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(hist, separators=(",", ":")), encoding="utf-8")


async def lowest_filter(page, cands, report, hist, today):
    """Kendi geçmişimiz yeterliyse onu, değilse Akakçe'yi kullanır."""
    to_akakce = []
    passed = []
    for p in cands:
        days, low = history_info(hist, p["url"], today)
        if days >= GECMIS_MIN_GUN and low is not None:
            ok = p["new"] is not None and p["new"] <= low
            why = f"{days} günün en düşüğü (kayıtlar)" if ok else f"{days} günde daha düşük görülmüş"
            report.append(f"{'✅' if ok else '✗'} {p['title'][:45]} | bizde {fmt_price(p['new'] or 0)} | "
                          f"kayıt en düşük {fmt_price(low)} | {why}")
            if ok:
                p["lowest_note"] = f"Son {days} günün en düşük fiyatı (kayıtlarımız)"
                passed.append(p)
        else:
            to_akakce.append(p)
    if to_akakce:
        for p in await akakce_filter(page, to_akakce, report):
            p["lowest_note"] = "Son 1 ayın en düşük fiyatı (Akakçe)"
            passed.append(p)
    return passed


async def scrape_category(page, name, base_url, site="Hepsiburada", pages=None):
    results, seen_count = [], 0
    pages = pages or SITE_PAGES.get(site, PAGES_PER_CATEGORY)
    for n in range(1, pages + 1):
        url = page_url(base_url, n, site)
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            status = resp.status if resp else "?"
            if status == 403:  # güvenlik engeli: bir kez bekleyip tekrar dene
                print(f"[{name}] 403, bekleyip tekrar deneniyor...")
                await page.wait_for_timeout(random.randint(15000, 25000))
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                status = resp.status if resp else "?"
            if site == "Trendyol":
                await trendyol_select_country(page)
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
        if SITE_TESHIS.get(site):
            SAMPLES.setdefault(name, cards[:2])
            await page.wait_for_timeout(random.randint(3000, 6000))
            continue
        for c in cards:
            old, new, disc = analyze_fields(c)
            if new:
                u = c["url"]
                PRICE_SEEN[u] = min(new, PRICE_SEEN.get(u, new))
            if disc >= MIN_DISCOUNT and disc < 95:
                results.append({"url": c["url"], "title": c["title"], "sepet": c.get("sepet"),
                                "old": old, "new": new, "disc": disc, "cat": name, "text": c["text"],
                                "bits": c.get("bits", [])})
        await page.wait_for_timeout(random.randint(3000, 6000))  # siteyi yormamak için
    return results, seen_count


def _send_one(chat_id, text, tries=0):
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": False},
        timeout=20,
    )
    if r.status_code == 429 and tries < 3:  # hız sınırı
        time.sleep(r.json().get("parameters", {}).get("retry_after", 5) + 1)
        return _send_one(chat_id, text, tries + 1)
    if not r.ok:
        print(f"Telegram hatası ({chat_id}):", r.text)
    return r.ok


def send_telegram(text: str):
    """Mesajı tüm alıcılara gönderir; en az birine ulaşırsa başarılı sayılır."""
    if DRY_RUN:
        print("---\n" + text)
        return True
    ok_any = False
    for cid in CHAT_IDS:
        ok_any = _send_one(cid, text) or ok_any
        if len(CHAT_IDS) > 1:
            time.sleep(0.4)
    return ok_any


def format_message(p) -> str:
    title = html.escape(p["title"][:150] or "Ürün")
    lines = [f"🔥 <b>%{p['disc']:.0f} indirim</b> · {html.escape(p['cat'])}", f"<b>{title}</b>"]
    if p["old"] and p["new"]:
        lines.append(f"<s>{fmt_price(p['old'])} TL</s> → <b>{fmt_price(p['new'])} TL</b>"
                     + (" (sepette)" if p.get("sepet") else ""))
    elif p["new"]:
        lines.append(f"<b>{fmt_price(p['new'])} TL</b>")
    if p.get("lowest_note"):
        lines.append("📉 " + html.escape(p["lowest_note"]))
    lines.append(p["url"])
    return "\n".join(lines)


def load_state():
    try:
        src = STATE_FILE if STATE_FILE.exists() else LEGACY_STATE
        data = json.loads(src.read_text(encoding="utf-8"))
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

    manual = os.environ.get("GITHUB_EVENT_NAME", "workflow_dispatch") == "workflow_dispatch"
    jobs = []  # (site, görünen ad, link, sayfa)
    for name, url in CATEGORIES.items():
        jobs.append(("Hepsiburada", name, url, PAGES_PER_CATEGORY))
    for name, url in HB_SUB_CATEGORIES.items():
        jobs.append(("Hepsiburada", name, url, HB_SUB_PAGES))
    for site, cats_ in (("Trendyol", TRENDYOL_CATEGORIES), ("N11", N11_CATEGORIES)):
        if SITE_TESHIS.get(site) and not manual:  # teşhis sadece elle çalıştırmada
            continue
        for name, url in cats_.items():
            jobs.append((site, name, url, SITE_PAGES.get(site, 1)))
    jobs = [j for j in jobs if j[2].startswith("http") and (not SITE or j[0] == SITE)]
    k, n_shards = (int(x) for x in SHARD.split("/"))
    jobs = [j for i, j in enumerate(jobs) if i % n_shards == k - 1]
    if not jobs:
        print("Bu iş için taranacak kategori yok.")
        return
    print(f"{len(jobs)} kategori taranacak ({SITE or 'tüm siteler'}, parça {SHARD}).")

    state = load_state()
    found, total_seen = [], 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True, channel="chromium",
            args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(
            locale="tr-TR", timezone_id="Europe/Istanbul",
            extra_http_headers={"Accept-Language": "tr-TR,tr;q=0.9"},
            viewport={"width": 1366, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
        )
        await ctx.add_cookies([
            {"name": n, "value": v, "domain": ".trendyol.com", "path": "/"}
            for n, v in (("countryCode", "TR"), ("storefrontId", "1"), ("language", "tr"))
        ])
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await ctx.new_page()
        site_counts = {}
        for site, name, url, pages in jobs:
            full = f"{site} · {name}"
            items, count = await scrape_category(page, full, url, site=site, pages=pages)
            total_seen += count
            site_counts[full] = count
            found += items
        state_pre = load_state()
        uniq_pre = {}
        for p in sorted(found, key=lambda p: -p["disc"]):
            if p["url"] not in state_pre and p["url"] not in uniq_pre:
                uniq_pre[p["url"]] = p
        akakce_report = []
        today = int(time.time() // 86400)
        hist = load_history()
        if AKAKCE_FILTRE and uniq_pre:
            passed = await lowest_filter(page, list(uniq_pre.values()), akakce_report, hist, today)
            found = passed
            print("En düşük fiyat kontrolü:\n" + "\n".join(akakce_report))
            if manual and akakce_report:
                head = "📊 En düşük fiyat kontrolü (" + html.escape(JOB_KEY or "tümü") + ")"
                chunk, part = [], 1
                for line in akakce_report + [None]:
                    if line is None or sum(len(x) + 1 for x in chunk) + len(line) > 3300:
                        if chunk:
                            send_telegram(f"{head} [{part}]:\n\n" + html.escape("\n".join(chunk)))
                            part += 1
                            time.sleep(1.2)
                        chunk = []
                    if line is not None:
                        chunk.append(line)
        elif AKAKCE_FILTRE:
            found = []
        update_history(hist, today)
        print(f"Fiyat geçmişi: {len(hist)} ürün kayıtlı, bu çalışmada {len(PRICE_SEEN)} fiyat görüldü.")
        if AKAKCE_TESHIS and manual and found:
            cands = sorted(found, key=lambda p: -p["disc"])
            report = await akakce_probe(page, cands)
            send_telegram("🔧 Akakçe teşhis (" + html.escape(JOB_KEY or "tümü") + "):\n\n"
                          + html.escape(report)[:3700])
        await browser.close()

    for site in ("Trendyol", "N11"):
        if not SITE_TESHIS.get(site):
            continue
        counts = {k: v for k, v in site_counts.items() if k.startswith(site)}
        if not counts:
            continue
        lines = [f"{k}: {v} ürün okundu" for k, v in counts.items()]
        for d in DIAG:
            if d.startswith(site) and d not in lines:
                lines.append(d)
        send_telegram(f"🔧 {site} teşhis:\n\n" + html.escape("\n".join(lines))[:3800])
        samples = [(n, c) for n, c in SAMPLES.items() if n.startswith(site)]
        for name, cards in samples[:3]:
            for c in cards[:1]:
                msg = (f"{name}\n{c['url']}\n\nKUTU METNİ:\n{c['text'][:900]}"
                       f"\n\nFİYAT ALANLARI:\n" + "\n".join(c.get("bits", [])))
                send_telegram(html.escape(msg[:3800]))
                time.sleep(1.2)

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
    try:
        status = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        status = {"engel": 0}
    if total_seen == 0:
        status["engel"] = status.get("engel", 0) + 1
        n = status["engel"]
        print(f"Erişim engellendi ({n}. kez arka arkaya).")
        if n == 3 or (n > 3 and (n - 3) % 24 == 0):
            detail = "\n\n".join(html.escape(d) for d in DIAG[:6])
            who = SITE or "Siteler"
            send_telegram(f"⚠️ {who} ({JOB_KEY or 'tümü'}) {n} çalışmadır arka arkaya okunamıyor. Teşhis:\n\n" + detail)
    else:
        if status.get("engel", 0) >= 3:
            send_telegram(f"✅ {SITE or 'Site'} erişimi tekrar sağlandı.")
        status["engel"] = 0
    STATUS_FILE.write_text(json.dumps(status), encoding="utf-8")

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
