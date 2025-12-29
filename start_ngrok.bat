@echo off
title eBay AI Assistant - Ngrok Tunnel

echo ===================================================
echo   Starting Ngrok Tunnel for eBay OAuth
echo ===================================================
echo.
echo [INFO] This is required for "Sign in with eBay" to work.
echo [INFO] Your public URL: https://secure-openly-moth.ngrok-free.app
echo.
echo forwarding to localhost:5000...
echo.

:: Check if ngrok exists
if not exist "ngrok.exe" (
    echo [ERROR] ngrok.exe not found in this folder!
    echo    Please download it from https://ngrok.com/download
    echo    and place it next to this script.
    pause
    exit /b 1
)

:: Run the specific command requested by user
.\ngrok http --url=secure-openly-moth.ngrok-free.app 5000
pause
