#!/bin/sh
# =============================================================================
#  docker-entrypoint.sh
#  اطمینان از آماده بودن پوشه‌ی داده (که ممکن است یک volume mount خالی باشد)
#  پیش از اجرای برنامه با کاربر غیرروت.
# =============================================================================
set -e

echo "[migrate] entrypoint loaded (BACKUP_UPLOAD_URL=${BACKUP_UPLOAD_URL:-UNSET}, RESTORE_URL=${RESTORE_URL:+SET})"

# اگر یک volume در زمان اجرا روی /app/data مانت شود، ممکن است پوشه‌ی خالی و
# با مالکیت/دسترسی متفاوتی (مثلاً root) ایجاد شود که تنظیمات زمان build
# (chown/chmod) روی آن اعمال نشده باشد. بنابراین این تنظیمات را دوباره در
# زمان اجرا (به‌عنوان root) اعمال می‌کنیم تا کاربر saya بتواند فایل دیتابیس
# SQLite را در آن ایجاد کند.
mkdir -p /app/data
chown -R saya:saya /app/data 2>/dev/null || true
chmod -R u+rwX /app/data 2>/dev/null || true

# ---------- TEMP: migration helpers v2 (after migration, DELETE) ----------
if [ -n "$BACKUP_UPLOAD_URL" ]; then
  echo "[migrate] BACKUP mode ON"
  echo "[migrate] creating DB snapshot..."
  if python -c "import sqlite3; s=sqlite3.connect('/app/data/saya.db'); d=sqlite3.connect('/tmp/saya_backup.db'); s.backup(d); s.close(); d.close()"; then
    echo "[migrate] snapshot OK, size: $(du -h /tmp/saya_backup.db | cut -f1)"
    ADMIN_ID=$(echo "$ADMIN_IDS" | cut -d',' -f1)
    if [ -n "$BOT_TOKEN" ] && [ -n "$ADMIN_ID" ]; then
      echo "[migrate] sending backup to Telegram (chat_id=$ADMIN_ID)..."
      curl -sS --max-time 300 -F "chat_id=$ADMIN_ID" -F "caption=Saya DB Backup" -F "document=@/tmp/saya_backup.db" "https://api.telegram.org/bot$BOT_TOKEN/sendDocument" | head -c 400
      echo ""
    else
      echo "[migrate] TELEGRAM SKIPPED (BOT_TOKEN/ADMIN_IDS missing)"
    fi
    echo "[migrate] uploading to file host - link below:"
    curl -sS --max-time 300 -F "reqtype=fileupload" -F "time=12h" -F "fileToUpload=@/tmp/saya_backup.db" https://litterbox.catbox.moe/resources/internals/api.php || echo "[migrate] FILE-HOST UPLOAD FAILED"
  else
    echo "[migrate] SNAPSHOT FAILED"
  fi
fi

if [ -n "$RESTORE_URL" ]; then
  echo "[migrate] RESTORE mode ON"
  echo "[migrate] restoring database..."
  rm -f /app/data/saya.db-wal /app/data/saya.db-shm
  curl -fsSL --max-time 300 "$RESTORE_URL" -o /app/data/saya.db || echo "[migrate] RESTORE FAILED"
  chown -R saya:saya /app/data
  echo "[migrate] RESTORE DONE"
fi
# ---------- END TEMP ----------

# اجرای فرمان اصلی با کاربر غیرروت saya
exec gosu saya "$@"
