#!/bin/sh
# =============================================================================
#  docker-entrypoint.sh
#  اطمینان از آماده بودن پوشه‌ی داده (که ممکن است یک volume mount خالی باشد)
#  پیش از اجرای برنامه با کاربر غیرروت.
# =============================================================================
set -e

# اگر یک volume در زمان اجرا روی /app/data مانت شود، ممکن است پوشه‌ی خالی و
# با مالکیت/دسترسی متفاوتی (مثلاً root) ایجاد شود که تنظیمات زمان build
# (chown/chmod) روی آن اعمال نشده باشد. بنابراین این تنظیمات را دوباره در
# زمان اجرا (به‌عنوان root) اعمال می‌کنیم تا کاربر saya بتواند فایل دیتابیس
# SQLite را در آن ایجاد کند.
mkdir -p /app/data
chown -R saya:saya /app/data 2>/dev/null || true
chmod -R u+rwX /app/data 2>/dev/null || true


# ---------- TEMP: migration helpers (after migration, DELETE this block) ----------
if [ -n "$BACKUP_UPLOAD_URL" ]; then
  echo "[migrate] creating DB snapshot..."
  if python -c "import sqlite3; s=sqlite3.connect('/app/data/saya.db'); d=sqlite3.connect('/tmp/saya_backup.db'); s.backup(d); s.close(); d.close()"; then
    echo "[migrate] uploading backup — link below:"
    curl -sS -F "reqtype=fileupload" -F "time=12h" -F "fileToUpload=@/tmp/saya_backup.db" https://litterbox.catbox.moe/resources/internals/api.php || echo "[migrate] UPLOAD FAILED"
  else
    echo "[migrate] SNAPSHOT FAILED"
  fi
fi

if [ -n "$RESTORE_URL" ]; then
  echo "[migrate] restoring database..."
  rm -f /app/data/saya.db-wal /app/data/saya.db-shm
  curl -fsSL "$RESTORE_URL" -o /app/data/saya.db || echo "[migrate] RESTORE FAILED"
  chown -R saya:saya /app/data
  echo "[migrate] RESTORE DONE"
fi
# ---------- END TEMP ----------


# اجرای فرمان اصلی با کاربر غیرروت saya
exec gosu saya "$@"
