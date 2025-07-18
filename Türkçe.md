# Deprem Uyarıları Discord Botu

ABD Jeolojik Araştırmalar Kurumu (USGS) kaynağından gerçek zamanlı deprem uyarıları sağlayan bir Discord botu. Kullanıcılar, belirli bölgelerde ve minimum bir büyüklüğün üzerinde gerçekleşen depremler için doğrudan mesaj almak üzere abone olabilir ve sunucu kanalı uyarılarını yapılandırabilirler.

## Özellikler

- 🌍 USGS'den gerçek zamanlı deprem uyarıları
- 📬 Bölge ve büyüklük tabanlı DM uyarıları için kullanıcı abonelikleri
- 🔔 Bölge ve büyüklük filtreleriyle sunucu kanal uyarıları
- 🗺️ Ülke bazında bölge seçimi ve otomatik tamamlama
- 🛡️ Yalnızca yöneticiye özel yapılandırma komutları
- 📝 Kolay kurulum: `.env` ve SQLite veritabanı ile

## Kurulum

### 1. Depoyu Klonlayın

```sh
git clone https://github.com/yourusername/Earthquake-Alerts.git
cd Earthquake-Alerts
```

### 2. Bağımlılıkları Yükleyin

Bilgisayarınızda Python 3.8+ kurulu olduğundan emin olun.

```sh
pip install -r requirements.txt
```

### 3. Ortam Değişkenlerini Yapılandırın

`.env.example` dosyasını `.env` olarak kopyalayın ve Discord bot tokeninizi ekleyin:

```sh
cp .env.example .env
```

`.env` dosyasını düzenleyin:

```env
DISCORD_TOKEN=your_bot_token_here
```

`your_bot_token_here` olan yeri kendi Discord botunuzun tokeni ile değiştirin.

### 4. Botu Çalıştırın

```sh
python bot.py
```

## Kullanım

### Sunucu Yönetici Komutları

- `/setchannel` — Sunucu için uyarı kanalı, bölge ve minimum büyüklüğü ayarlayın.
- `/removechannel` — Uyarı kanalı yapılandırmasını kaldırın.
- `/status` — Sunucunun mevcut uyarı ayarlarını gösterir.

### Kullanıcı Komutları

- `/subscribe` — Seçilen bölge ve minimum büyüklükteki depremler için DM alın.
- `/unsubscribe` — DM uyarılarını durdurun.
- `/help` — Yardım ve kullanım talimatlarını gösterir.

### Geliştirici/Test Komutları

- `/faketest` — Sahte bir deprem uyarısı gönderir (yalnızca geliştirici için).
- `/sync` — Slash komutlarının yeniden senkronize edilmesini sağlar (yalnızca geliştirici için).

## Veri Dosyaları

- [countries.json](countries.json) — Bölge filtrelemesi için ülke sınır kutularını içerir.
- [countries.csv](countries.csv) — Ülke sınır kutuları için referansları içerir.
- [botdata.db](botdata.db) / [config.db](config.db) — Yapılandırma ve abonelikleri saklamak için SQLite veritabanlarını içerir.

## Bağımlılıklar

Tam liste için [`requirements.txt`](requirements.txt) dosyasına bakınız.

Ana paketler:

- `discord.py`
- `requests`
- `python-dotenv`
- `pycountry`
- `sqlite3` (standart kütüphane)
- [Railway](https://railway.app/) ile hosting hizmeti (isteğe bağlı)

## Lisans

MIT Lisansı kullanılmıştır. Detaylar için [`LICENSE`](LICENSE) dosyasına bakınız.

---

En hızlı deprem bilgisi için 💙 ile yapıldı. Güvende kalın!
