@echo off
title Construction de Retminal
echo ============================================
echo    Construction de Retminal.exe
echo ============================================
echo.

echo Verification des modules necessaires...
pip install pyinstaller paramiko pillow
echo.

pyinstaller --onefile --noconsole --name Retminal --icon "Retminal.ico" --add-data "Retminal.ico;." --add-data "Retminal_icone.png;." retminal.py

echo.
echo N'oublie pas de mettre le fichier .env a cote de Retminal.exe !

echo.
echo ============================================
echo    Termine ! Ton Retminal.exe est dans : dist\Retminal.exe
echo ============================================
pause
