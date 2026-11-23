#!/usr/bin/env bash
# Pemakaian: extract_frontend.sh app.exe outdir
set -u
APP="$1"; OUT="$2"
rm -rf "$OUT"; mkdir -p work
if command -v untauri >/dev/null; then
  untauri inspect "$APP" > work/inspect.txt 2>&1 || true
  if untauri "$APP" -o "$OUT" --tree && [ -f "$OUT/index.html" ]; then
    rm -f "$OUT/assets.json"; echo "untauri OK"; exit 0
  fi
  echo "untauri gagal, mencoba scanner brotli..."
fi
rm -rf "$OUT"
python3 "$(dirname "$0")/extract_tauri_assets.py" "$APP" "$OUT" && exit 0
exit 1
