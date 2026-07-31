# راهنمای توسعه‌دهندگان

## محیط توسعه

### پیش‌نیازها

- Python 3.12+
- Poetry 1.8+
- Git

### راه‌اندازی

```bash
git clone <repo-url>
cd saya-bot
poetry install
cp .env.example .env
# ویرایش .env
poetry run alembic upgrade head
```

### ساختار کدنویسی

#### Type Hints
تمام کدها باید type hint کامل داشته باشند:
```python
async def get_user(self, telegram_id: int) -> User | None:
    ...
```

#### Docstring
تمام توابع و کلاس‌ها باید docstring فارسی داشته باشند:
```python
def compute_risk_score(*, reports_count: int = 0) -> int:
    """محاسبه‌ی امتیاز ریسک کاربر.

    Args:
        reports_count: تعداد گزارش‌های فعال.

    Returns:
        عدد صحیح بین ۰ تا ۱۰۰.
    """
```

#### نام‌گذاری
- کلاس‌ها: `PascalCase` (مثلاً `UserService`)
- توابع و متغیرها: `snake_case` (مثلاً `get_by_telegram_id`)
- ثابت‌ها: `UPPER_CASE` (مثلاً `DEFAULT_LOCALE`)
- ماژول‌ها: `snake_case` (مثلاً `user_service.py`)

## گردش کار توسعه

### ۱. ساخت شاخه
```bash
git checkout -b feature/new-feature
```

### ۲. نوشتن کد
- از الگوی موجود پیروی کنید
- اگر منطق جدید است، سرویس جدید بسازید
- از کد تکراری پرهیز کنید (DRY)

### ۳. نوشتن تست
```python
@pytest.mark.unit
class TestNewFeature:
    async def test_basic(self, db_manager):
        ...
```

### ۴. بررسی کیفیت
```bash
poetry run ruff check src/ tests/
poetry run ruff format src/ tests/
poetry run pytest -v
```

### ۵. Commit و Push
```bash
git add .
git commit -m "feat: توضیح ویژگی جدید"
git push origin feature/new-feature
```

## افزودن ویژگی جدید

### مثال: افزودن سرویس جدید

۱. ساخت فایل `src/anonchat/services/my_service.py`:
```python
class MyService:
    def __init__(self, container: Container) -> None:
        self._container = container

    async def do_something(self, telegram_id: int) -> None:
        ...
```

۲. افزودن به کانتینر (`core/container.py`):
```python
@property
def my_service(self) -> MyService:
    from anonchat.services.my_service import MyService
    if not hasattr(self, "_my_service"):
        self._my_service = MyService(self)
    return self._my_service
```

۳. استفاده در هندلر:
```python
container = get_container()
await container.my_service.do_something(message.from_user.id)
```

### مثال: افزودن هندلر جدید

۱. ساخت فایل در `bot/handlers/my_handler.py`:
```python
from aiogram import Router

router = Router()

@router.message(F.text == "دکمه من")
async def my_handler(message: Message):
    ...
```

۲. ثبت در `bot/handlers/__init__.py`:
```python
from anonchat.bot.handlers import my_handler
router.include_router(my_handler.router)
```

### مثال: افزودن مدل جدید

۱. ساخت فایل در `models/my_model.py`:
```python
class MyModel(Base, TimestampMixin):
    __tablename__ = "my_models"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ...
```

۲. ثبت در `models/__init__.py`:
```python
from anonchat.models.my_model import MyModel
__all_models__.append(MyModel)
```

۳. ساخت مهاجرت:
```bash
poetry run alembic revision --autogenerate -m "add my_model"
poetry run alembic upgrade head
```

## تست‌نویسی

### تست واحد
```python
@pytest.mark.unit
class TestMyFeature:
    def test_basic(self):
        assert my_function() == expected
```

### تست با دیتابیس
```python
@pytest.mark.unit
class TestMyRepo:
    async def test_create(self, db_manager, sample_user):
        repo = db_manager.my_repo()
        ...
```

### تست یکپارچه
```python
@pytest.mark.integration
class TestFullFlow:
    async def test_end_to_end(self, db_manager):
        ...
```

## دیباگ

### فعال‌سازی لاگ DEBUG
```env
LOG_LEVEL=DEBUG
LOG_FORMAT=console
```

### بررسی دیتابیس
```bash
sqlite3 data/saya.db
.tables
SELECT * FROM users LIMIT 5;
```

### پروفایلینگ
```python
import cProfile
cProfile.run("main()", "profile.prof")
```

## انتشار

### نسخه‌گذاری
از Semantic Versioning استفاده می‌کنیم: `MAJOR.MINOR.PATCH`

### CI/CD
- هر push به `main` → استقرار روی Railway
- هر PR → اجرای تست‌ها در GitHub Actions
