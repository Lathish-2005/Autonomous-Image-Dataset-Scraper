@echo off
REM ================================================================
REM  Car Dataset Pipeline - Full Dependency Setup Script (Windows)
REM  Run this on a new system to install everything needed.
REM ================================================================

echo.
echo ============================================================
echo   CAR DATASET PIPELINE - DEPENDENCY INSTALLER
echo ============================================================
echo.

REM Check Python version
python --version 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo         Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo [Step 1/4] Installing core Python dependencies...
echo ─────────────────────────────────────────────────
pip install playwright>=1.40.0 beautifulsoup4>=4.12.0 lxml>=4.9.0 requests>=2.31.0 ultralytics>=8.0.0 opencv-python>=4.8.0 numpy>=1.24.0 Pillow>=10.0.0 openpyxl>=3.1.0 pandas>=2.0.0 imagehash>=4.3.0 tqdm>=4.65.0

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install core dependencies.
    pause
    exit /b 1
)

echo.
echo [Step 2/4] Installing optional dependencies...
echo ─────────────────────────────────────────────────
pip install playwright-stealth>=1.0.0 yt-dlp>=2024.1.0 kaggle>=1.5.0

echo.
echo [Step 3/4] Installing Playwright Chromium browser...
echo ─────────────────────────────────────────────────
playwright install chromium

if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Playwright browser install failed.
    echo           You can retry manually: playwright install chromium
)

echo.
echo [Step 4/4] Verifying installation...
echo ─────────────────────────────────────────────────
python -c "import playwright; print('  [OK] playwright', playwright.__version__)"
python -c "import bs4; print('  [OK] beautifulsoup4')"
python -c "import requests; print('  [OK] requests', requests.__version__)"
python -c "import ultralytics; print('  [OK] ultralytics', ultralytics.__version__)"
python -c "import cv2; print('  [OK] opencv-python', cv2.__version__)"
python -c "import numpy; print('  [OK] numpy', numpy.__version__)"
python -c "import PIL; print('  [OK] Pillow', PIL.__version__)"
python -c "import openpyxl; print('  [OK] openpyxl', openpyxl.__version__)"
python -c "import pandas; print('  [OK] pandas', pandas.__version__)"
python -c "import imagehash; print('  [OK] imagehash')"
python -c "import tqdm; print('  [OK] tqdm', tqdm.__version__)"
python -c "import lxml; print('  [OK] lxml')"
python -c "import yt_dlp; print('  [OK] yt-dlp', yt_dlp.version.__version__)" 2>nul

echo.
echo ============================================================
echo   INSTALLATION COMPLETE!
echo ============================================================
echo.
echo   To run the car pipeline:
echo     cd car_pipeline
echo     python main.py --make Toyota --headed
echo.
echo   To run the YouTube agent:
echo     cd "sandeep agent"
echo     python main.py --make Honda --browser chrome
echo.
pause
