@echo off
title MOKADU WhatsApp Bot
echo.
echo  ==========================================
echo   MOKADU WhatsApp Bot -- Servidor Python
echo  ==========================================
echo.
echo  El servidor escucha en http://localhost:8000
echo  Ctrl+C para parar
echo.
cd /d "%~dp0"
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
pause
