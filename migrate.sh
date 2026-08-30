#!/bin/sh
# MIGRATE helper: backup on old account / restore on new account
# Runs before the bot starts. Controlled via env vars. Always exits 0.

echo "MIGRATE: helper loaded (BACKUP_UPLOAD_URL=${BACKUP_UPLOAD_URL:-UNSET}, RESTORE_URL=${RESTORE_URL:+SET})"

if test -n "$BACKUP_UPLOAD_URL"; then
  echo "MIGRATE: BACKUP mode ON"
  echo "MIGRATE: creating DB snapshot..."
  if python -c "import sqlite3; s=sqlite3.connect('/app/data/saya.db'); d=sqlite3.connect('/tmp/saya_backup.db'); s.backup(d); s.close(); d.close()"; then
    echo "MIGRATE: snapshot OK, size: $(du -h /tmp/saya_backup.db | cut -f1)"
    ADMIN_ID=$(echo "$ADMIN_IDS" | cut -d',' -f1)
    if test -n "$BOT_TOKEN" && test -n "$ADMIN_ID"; then
      echo "MIGRATE: sending backup to Telegram (chat_id=$ADMIN_ID)..."
      curl -sS --max-time 300 -F "chat_id=$ADMIN_ID" -F "caption=Saya DB Backup" -F "document=@/tmp/saya_backup.db" "https://api.telegram.org/bot$BOT_TOKEN/sendDocument" | head -c 400
      echo ""
    else
      echo "MIGRATE: TELEGRAM SKIPPED (BOT_TOKEN/ADMIN_IDS missing)"
    fi
    echo "MIGRATE: uploading to file host - link below:"
    curl -sS --max-time 300 -F "reqtype=fileupload" -F "time=12h" -F "fileToUpload=@/tmp/saya_backup.db" https://litterbox.catbox.moe/resources/internals/api.php || echo "MIGRATE: FILE-HOST UPLOAD FAILED"
  else
    echo "MIGRATE: SNAPSHOT FAILED"
  fi
fi

if test -n "$RESTORE_URL"; then
  echo "MIGRATE: RESTORE mode ON"
  echo "MIGRATE: restoring database..."
  rm -f /app/data/saya.db-wal /app/data/saya.db-shm
  curl -fsSL --max-time 300 "$RESTORE_URL" -o /app/data/saya.db || echo "MIGRATE: RESTORE FAILED"
  chown -R saya:saya /app/data 2>/dev/null || true
  echo "MIGRATE: RESTORE DONE"
fi

exit 0
