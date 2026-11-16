# Hepsiburada İndirim Botu

Bilgisayar, Süpermarket, Kozmetik, Kişisel Bakım, Yapı Market ve Oto Aksesuar kategorilerini
3 saatte bir tarar, %30 ve üzeri indirimli ürünleri Telegram'a gönderir.

## Kurulum

1. **Telegram botu oluştur:** Telegram'da @BotFather'a `/newbot` yaz, adımları izle, verdiği **token**'ı kaydet.
2. **Chat ID'ni öğren:** Yeni botuna herhangi bir mesaj at. Sonra tarayıcıda
   `https://api.telegram.org/bot<TOKEN>/getUpdates` adresini aç. `"chat":{"id":123456789` kısmındaki sayı chat ID'ndir.
3. **GitHub'da yeni bir depo (repository) aç** ve bu klasördeki dosyaları yükle.
   `.github/workflows/indirim-bot.yml` dosyası gizli klasörde olduğu için sürükle-bırakta görünmeyebilir;
   bu durumda GitHub'da *Add file → Create new file* deyip adına `.github/workflows/indirim-bot.yml` yaz ve içeriği yapıştır.
4. **Kategori linklerini ekle:** Hepsiburada'da her kategoriye gir, adres çubuğundaki linki kopyala ve
   `bot.py` dosyasının başındaki `CATEGORIES` listesinde ilgili `BURAYA_LINK_YAPISTIR` yerine yapıştır.
5. **Gizli bilgileri ekle:** Depoda *Settings → Secrets and variables → Actions → New repository secret*:
   - `TELEGRAM_BOT_TOKEN` → BotFather'ın verdiği token
   - `TELEGRAM_CHAT_ID` → chat ID'n
6. **Test et:** *Actions* sekmesi → *Hepsiburada İndirim Botu* → *Run workflow*. Bitince Telegram'ı kontrol et.

Sonrasında bot 3 saatte bir kendiliğinden çalışır.

## Ayarlar (bot.py başında)
- `MIN_DISCOUNT` – minimum indirim yüzdesi (varsayılan 30)
- `PAGES_PER_CATEGORY` – her kategoride taranacak sayfa sayısı (varsayılan 3)
- `MAX_MESSAGES_PER_RUN` – bir seferde en fazla gönderilecek mesaj (varsayılan 40)
- Çalışma sıklığı: `.github/workflows/indirim-bot.yml` içindeki `cron` satırı

## Notlar
- Gizli (private) depolarda GitHub ayda 2.000 dakika ücretsiz verir; 3 saatte bir çalışma bunun içinde kalır.
- Uzun süre depoda hiçbir değişiklik olmazsa GitHub zamanlanmış görevleri durdurabilir; böyle olursa Actions sekmesinden tekrar etkinleştir.
- "Hiç ürün okunamadı" uyarısı gelirse kategori linklerini kontrol et; linkler doğruysa Hepsiburada GitHub sunucularını engelliyor olabilir.
