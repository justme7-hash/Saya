# syntax=docker/dockerfile:1.7
# =============================================================================
#  Dockerfile ربات سایه
#  چندمرحله‌ای برای کاهش حجم تصویر نهایی
# =============================================================================

# --- مرحله 1: builder ---------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.8.4 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_VIRTUALENVS_CREATE=true

# Install build-essential for compiling C extensions (e.g., uvloop)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# کپی فقط فایل‌های وابستگی برای کش بهتر
COPY pyproject.toml ./
# اگر poetry.lock وجود دارد کپی کن (در صورت نبودن، poetry خودش می‌سازد)
COPY poetry.lock* ./

# نصب وابستگی‌ها (بدون نصب پروژه خودمان)
RUN poetry install --no-root --without dev --no-interaction

# --- مرحله 2: runtime ---------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src"

# نصب ca-certificates برای اتصال HTTPS به تلگرام و gosu برای تعویض کاربر در entrypoint
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl gosu && \
    rm -rf /var/lib/apt/lists/*

# ایجاد کاربر غیرروت برای امنیت
RUN groupadd -r saya && useradd -r -g saya -d /app -s /sbin/nologin saya

WORKDIR /app

# کپی محیط مجازی از builder
COPY --from=builder --chown=saya:saya /app/.venv /app/.venv

# کپی کد پروژه
COPY --chown=saya:saya src/ /app/src/
COPY --chown=saya:saya alembic/ /app/alembic/
COPY --chown=saya:saya alembic.ini /app/
COPY --chown=saya:saya pyproject.toml /app/

# ایجاد پوشه‌ی داده
RUN mkdir -p /app/data && chown saya:saya /app/data

# کپی entrypoint که در زمان اجرا مالکیت/دسترسی /app/data را (حتی اگر توسط
# یک volume mount خالی و با مالکیت root بازنویسی شده باشد) تضمین می‌کند
COPY --chown=root:root docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# توجه: با وجود entrypoint، کانتینر ابتدا با root شروع می‌شود تا مجوزهای
# /app/data تصحیح شود و سپس با gosu به کاربر saya سوییچ می‌کند
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${HEALTH_PORT:-8080}/health || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]

# اجرای ربات
CMD ["python", "-m", "anonchat.main"]
