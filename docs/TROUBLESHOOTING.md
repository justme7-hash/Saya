# راهنمای رفع خطا

## خطاهای راه‌اندازی

### `ValidationError: bot_token Field required`
**علت**: متغیر `BOT_TOKEN` تنظیم نشده است.
**راه‌حل**: فایل `.env` را بسازید و توکن را وارد کنید:
```bash
cp .env.example .env
# ویرایش .env
BOT_TOKEN=123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### `ValidationError: ADMIN_IDS`
**علت**: حداقل یک مدیر مشخص نشده است.
**راه‌حل**: شناسه تلگرام خود را اضافه کنید. برای یافتن شناسه:
- به [@userinfobot](https://t.me/userinfobot) بفرستید
- یا از ربات [@getmyid_bot](https://t.me/getmyid_bot) استفاده کنید

### `ModuleNotFoundError: No module named 'anonchat'`
**علت**: مسیر src در PYTHONPATH نیست.
**راه‌حل**:
```bash
export PYTHONPATH="/path/to/saya-bot/src:$PYTHONPATH"
# یا با Poetry:
poetry install
poetry run python -m anonchat.main
```

### `alembic.util.exc.CommandError`
**علت**: مشکل در مهاجرت دیتابیس.
**راه‌حل**:
```bash
# بررسی وضعیت مهاجرت
alembic current

# بازگشت به مهاجرت قبلی
alembic downgrade -1

# اجرای مجدد
alembic upgrade head
```

## خطاهای اجرا

### `aiogram.utils.exceptions.Unauthorized`
**علت**: توکن ربات نامعتبر است.
**راه‌حل**: توکن را در BotFather بررسی/reset کنید.

### `aiogram.utils.exceptions.NetworkError`
**علت**: مشکل اتصال به سرورهای تلگرام.
**راه‌حل**:
- اتصال اینترنت را بررسی کنید
- اگر از ایران هستید، ممکن است نیاز به VPN/پروکسی باشد

### `sqlalchemy.exc.OperationalError: no such table`
**علت**: جداول دیتابیس ساخته نشده‌اند.
**راه‌حل**:
```bash
alembic upgrade head
# یا
python -c "
import asyncio
from anonchat.core.container import get_container
async def main():
    c = get_container()
    await c.init()
    await c.db_manager.create_tables()
asyncio.run(main())
"
```

### `TypeError: can't compare offset-naive and offset-aware datetimes`
**علت**: SQLite datetimeها را naive ذخیره می‌کند.
**راه‌حل**: این مشکل در کد مدیریت شده (متد `is_expired`). اگر در جای دیگری
رخ داد، timezone را اضافه کنید:
```python
if dt.tzinfo is None:
    dt = dt.replace(tzinfo=UTC)
```

### `RuntimeError: Event loop is closed`
**علت**: استفاده نادرست از event loop در async.
**راه‌حل**: مطمئن شوید `asyncio.run()` فقط یک‌بار در entry point فراخوانی می‌شود.

## خطاهای ربات

### ربات پاسخ نمی‌دهد
1. بررسی کنید ربات در BotFather فعال باشد
2. بررسی کنید `MAINTENANCE_MODE=false`
3. بررسی کنید کاربر بن نباشد (با اکانت مدیر تست کنید)
4. لاگ‌ها را بررسی کنید

### کاربر نمی‌تواند ثبت‌نام کند
1. بررسی کنید کاربر قبلاً ثبت‌نام نکرده باشد
2. بررسی کنید ورودی‌ها معتبر باشند (سن ۱۳-۱۲۰، کد کشور ۲ حرف)
3. اگر خطای دیتابیس است، مهاجرت‌ها را بررسی کنید

### مچ‌سازی انجام نمی‌شود
1. بررسی کنید کاربران آنلاین و `is_searching=True` باشند
2. بررسی کنید کاربران در گفتگو نباشند
3. بررسی کنید فیلترها خیلی سختگیرانه نباشند
4. اگر کاربر در صف است، منتظر بمانید یا معیارها را放宽 کنید

### پیام رله نمی‌شود
1. بررسی کنید کاربر در گفتگوی فعال باشد (`is_in_chat=True`)
2. بررسی کنید نوع پیام پشتیبانی شود
3. بررسی کنید شریک بن/بلاک نباشد
4. لاگ‌های `service.message` را بررسی کنید

## خطاهای Railway

### Build ناموفق
- بررسی کنید `Dockerfile` در ریشه باشد
- بررسی کنید `pyproject.toml` معتبر باشد
- لاگ‌های build را در پنل Railway ببینید

### Health Check ناموفق
- بررسی کنید `HEALTH_PORT` با پورت Railway هماهنگ باشد
- بررسی کنید endpoint `/health` پاسخ ۲۰۰ بدهد
- بررسی کنید دیتابیس در دسترس باشد

### Memory Limit Exceeded
- پلن رایگان ۵۱۲MB RAM دارد
- اگر حافظه پر می‌شود:
  - کش‌ها را کوچک‌تر کنید
  - تعداد کاربران در صف را محدود کنید
  - لاگ‌ها را کمتر ذخنی کنید

## ابزارهای دیباگ

### فعال‌سازی لاگ DEBUG
```env
LOG_LEVEL=DEBUG
LOG_FORMAT=console
```

### بررسی دیتابیس
```bash
# SQLite
sqlite3 data/saya.db
.tables
SELECT * FROM users WHERE telegram_id = YOUR_ID;
SELECT * FROM chat_sessions WHERE status = 'active';
SELECT * FROM bans WHERE is_active = 1;

# خروجی
.quit
```

### تست دستی API
```bash
# Health check
curl http://localhost:8080/health

# آمار
curl http://localhost:8080/
```

### پاک‌سازی داده‌ی تست
```bash
rm data/saya.db
alembic upgrade head
```

## دریافت کمک

اگر مشکل خود را حل نکردید:
1. لاگ کامل خطا را ذخیره کنید
2. نسخه Python و Poetry را چک کنید
3. در Issues مخزن GitHub مشکل را گزارش دهید
4. شامل: خطا، لاگ، نسخه، سیستم‌عامل
