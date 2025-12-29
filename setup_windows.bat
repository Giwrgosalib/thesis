@echo off
setlocal
title eBay AI Assistant - One-Click Installer

echo ===================================================
echo   eBay AI Assistant - Unified Installer (Windows)
echo ===================================================
echo.

:: 1. Check Prerequisites
echo [1/6] Checking prerequisites...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH. Please install Python 3.10+.
    pause
    exit /b 1
)
call npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js/npm is not installed. Please install Node.js (LTS).
    pause
    exit /b 1
)
echo    - Python: Detected
echo    - Node.js: Detected

:: 2. Create Virtual Environment
if not exist "venv" (
    echo [2/6] Creating Python virtual environment...
    python -m venv venv
) else (
    echo [2/6] Virtual environment already exists.
)

:: 3. Activate & Upgrade pip
echo [3/6] Activating venv and updating pip...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip

:: 4. Install GPU PyTorch first (Critical for NextGen)
echo [4/6] Installing NVIDIA GPU support (PyTorch CUDA 12.1)...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo [4/6] Installing remaining backend dependencies...
pip install -r backend/requirements.txt

:: 5. Install Frontend Dependencies
echo [5/6] Installing frontend dependencies (Vue.js)...
cd frontend
call npm install
cd ..

:: 6. Check Configuration
echo [6/6] Checking for credentials...
if not exist "ebay-credentials.yaml" (
    echo.
    echo [WARNING] 'ebay-credentials.yaml' is missing!
    echo    Please create this file in the root folder with your eBay API keys.
    echo    See docs_notes/GPU_SETUP.md for the template.
    echo.
) else (
    echo    - Credentials found.
)

echo.
if not exist "ngrok.exe" (
    echo [WARNING] 'ngrok.exe' is missing!
    echo    You need this for the eBay Redirect URL.
    echo    Download it and place it in this folder.
) else (
    echo    - Ngrok found.
)

echo.
echo ===================================================
echo   Installation Complete!
echo ===================================================
echo.
echo Step 1: Start the Tunnel (Admin Terminal)
echo   start_ngrok.bat
echo.
echo Step 2: Run the App
echo   python scripts/start_dev.py
echo.
pause
