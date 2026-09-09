@echo off
setlocal
cd /d %~dp0

echo [setup] Creating folders...
if not exist downloads mkdir downloads
if not exist logs mkdir logs
if not exist fonts mkdir fonts

echo [setup] Creating venv...
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist fonts\DejaVuSans.ttf (
  echo [setup] Please place DejaVuSans.ttf into fonts\ 
  echo Download: https://dejavu-fonts.github.io/Download.html
  if exist C:\Windows\Fonts\arial.ttf (
    echo [setup] Fallback note: PDF may use Arial if you copy it manually as fonts\DejaVuSans.ttf is preferred
  )
)

if not exist .env (
  copy .env.example .env >nul
  echo [setup] Created .env — fill TELEGRAM_BOT_TOKEN and DEEPSEEK_API_KEY
)

echo [setup] Syntax check...
python -m py_compile bot.py config.py
for %%f in (services\*.py handlers\*.py) do python -m py_compile %%f

echo [setup] Done. Run: .venv\Scripts\activate ^&^& python bot.py
endlocal
