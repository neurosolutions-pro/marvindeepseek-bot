#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "[setup] Creating folders..."
mkdir -p downloads logs fonts

echo "[setup] Creating venv..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[setup] Installing system hints (optional)..."
if command -v apt-get >/dev/null 2>&1; then
  echo "  Suggested: sudo apt-get install -y tesseract-ocr tesseract-ocr-rus ffmpeg fonts-dejavu-core"
fi

FONT_DST="$ROOT/fonts/DejaVuSans.ttf"
if [ ! -f "$FONT_DST" ]; then
  if [ -f /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf ]; then
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf "$FONT_DST"
    echo "[setup] Copied system DejaVuSans.ttf"
  else
    echo "[setup] Downloading DejaVu fonts..."
    TMP="$(mktemp -d)"
    curl -fsSL -o "$TMP/dejavu.zip" \
      "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip"
    python3 - <<PY
import zipfile
from pathlib import Path
zf = zipfile.ZipFile("$TMP/dejavu.zip")
for name in zf.namelist():
    if name.endswith("DejaVuSans.ttf"):
        Path("$FONT_DST").write_bytes(zf.read(name))
        print("extracted", name)
        break
else:
    raise SystemExit("DejaVuSans.ttf not found in archive")
PY
    rm -rf "$TMP"
  fi
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[setup] Created .env from .env.example — заполните токены"
fi

echo "[setup] Syntax check..."
python -m py_compile bot.py config.py
python -m py_compile services/*.py handlers/*.py

echo "[setup] Done. Activate: source .venv/bin/activate && python bot.py"
