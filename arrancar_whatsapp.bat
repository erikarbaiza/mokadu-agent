@echo off
title MOKADU WhatsApp (Baileys)
echo.
echo  ==========================================
echo   MOKADU WhatsApp Bot -- Bridge WhatsApp
echo  ==========================================
echo.
echo  IMPORTANTE: Primero debes tener corriendo arrancar_bot.bat
echo.
echo  Escanea el QR con el movil del restaurante:
echo    WhatsApp - Tres puntos - Dispositivos vinculados - Vincular dispositivo
echo.
cd /d "%~dp0baileys"
npm start
pause
