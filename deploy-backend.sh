#!/bin/bash
set -e
cd "$(dirname "$0")"

SERVER="jochoa@54.202.41.70"

echo "=== Exportando BD ==="
sudo -u postgres pg_dump -d digiapps -n leyesmx > /tmp/backup_leyesmx.sql
scp /tmp/backup_leyesmx.sql "$SERVER:~"
rm /tmp/backup_leyesmx.sql

echo "=== Restaurando BD en servidor ==="
ssh -t "$SERVER" '
  sudo -u postgres psql -d digiapps -c "DROP SCHEMA IF EXISTS leyesmx CASCADE;"
  sudo -u postgres psql -d digiapps < ~/backup_leyesmx.sql
  rm ~/backup_leyesmx.sql
  sudo systemctl restart postgrest
'

echo "=== Subiendo PDFs ==="
ssh -t "$SERVER" 'sudo mkdir -p /var/www/leyesmx/pdfs && sudo chown $USER:$USER /var/www/leyesmx/pdfs'
TMP=$(mktemp -d)
for dir in backend/etl/data/*/; do
  ley=$(basename "$dir")
  [ -L "$dir/documento.pdf" ] && mkdir -p "$TMP/$ley" && cp -L "$dir/documento.pdf" "$TMP/$ley/"
done
scp -r "$TMP"/* "$SERVER:/var/www/leyesmx/pdfs/"
rm -rf "$TMP"

echo "✓ Backend actualizado"
