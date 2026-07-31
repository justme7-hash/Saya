# راهنمای استقرار

## Railway (توصیه‌شده — رایگان)

### مراحل

1. **ساخت ربات در BotFather**
   - به [@BotFather](https://t.me/BotFather) بروید
   - `/newbot` بفرستید
   - نام و username انتخاب کنید
   - توکن را کپی کنید

2. **آماده‌سازی مخزن GitHub**
   - پروژه را به GitHub push کنید
   - مطمئن شوید `.env` در `.gitignore` است

3. **ساخت پروژه در Railway**
   - به [railway.app](https://railway.app) بروید و وارد شوید
   - `New Project` → `Deploy from GitHub repo`
   - مخزن خود را انتخاب کنید

4. **تنظیم متغیرهای محیطی**
   در تب `Variables` این مقادیر را اضافه کنید:
   ```
   BOT_TOKEN=123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ADMIN_IDS=123456789
   DATABASE_URL=sqlite+aiosqlite:///./data/saya.db
   LOG_LEVEL=INFO
   LOG_FORMAT=json
   DEFAULT_LOCALE=fa
   HEALTH_PORT=8080
   MAINTENANCE_MODE=false
   ```

5. **افزودن Volume** (برای ماندگاری SQLite)
   - تب `Settings` → `Volumes`
   - مسیر `/app/data` را اضافه کنید

6. **استقرار**
   - Railway به‌طور خودکار `railway.json` را می‌خواند
   - Docker image می‌سازد و اجرا می‌کند
   - پس از چند دقیقه، ربات آماده است

7. **بررسی سلامت**
   - در تب `Deployments`، لاگ‌ها را بررسی کنید
   - باید پیام `main.polling_started` را ببینید

### محدودیت‌های پلن رایگان Railway

- **RAM**: 512MB
- **CPU**: 0.5 vCPU
- **اجرای ماهانه**: 500 ساعت (کافی برای 24/7)
- **Sleep**: پس از ۱۵ دقیقه غیرفعالی متوقف نمی‌شود (برخلاف برخی سرویس‌ها)

این ربات برای این محدودیت‌ها بهینه‌سازی شده است:
- SQLite سبک و کم‌مصرف
- Long Polling به‌جای Webhook
- کش درون‌حافظه‌ای برای کاهش کوئری دیتابیس

## Docker Compose (محلی)

```bash
docker-compose up -d
```

برای مشاهده‌ی لاگ:
```bash
docker-compose logs -f bot
```

برای توقف:
```bash
docker-compose down
```

## PostgreSQL (اختیاری)

برای پروداکشن بزرگ‌تر، می‌توانید از PostgreSQL رایگان استفاده کنید:

### گزینه‌های رایگان
- [Neon](https://neon.tech) — 0.5GB رایگان
- [Supabase](https://supabase.com) — 500MB رایگان
- [Aiven](https://aiven.io) — پلن رایگان محدود

### تنظیم
1. یک دیتابیس بسازید
2. `DATABASE_URL` را تنظیم کنید:
   ```
   DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
   ```
3. مهاجرت‌ها را اجرا کنید:
   ```bash
   alembic upgrade head
   ```

> **نکته:** برای PostgreSQL باید `asyncpg` نصب باشد:
> `pip install asyncpg`

## VPS (اختیاری)

اگر VPS دارید:

```bash
# نصب Docker
curl -fsSL https://get.docker.com | sh

# کلون پروژه
git clone <repo-url>
cd saya-bot

# تنظیم env
cp .env.example .env
nano .env

# اجرا
docker-compose up -d

# تنظیم systemd برای اجرای خودکار
sudo nano /etc/systemd/system/saya-bot.service
```

## پایش

### Health Check
ربات یک endpoint سلامت‌سنج روی `/health` ارائه می‌دهد:
```bash
curl http://localhost:8080/health
```

پاسخ:
```json
{
  "status": "healthy",
  "database": true,
  "bot_running": true,
  "maintenance_mode": false,
  "uptime_seconds": 3600,
  "version": "1.0.0"
}
```

### لاگ‌ها
- در Railway: تب `Deployments` → `Logs`
- در Docker: `docker-compose logs -f`
- با JSON format: قابل پردازش توسط ELK / Loki

### پشتیبان‌گیری
برای SQLite:
```bash
# کپی فایل دیتابیس
cp data/saya.db data/saya_backup_$(date +%Y%m%d).db
```

برای PostgreSQL:
```bash
pg_dump -U user -h host dbname > backup.sql
```

## به‌روزرسانی

```bash
# کش کردن تغییرات
git pull origin main

# اجرای مهاجرت‌ها (اگر تغییر کرده)
poetry run alembic upgrade head

# ری‌استارت
docker-compose restart bot
# یا در Railway: Railway به‌طور خودکار ری‌استارت می‌کند
```
