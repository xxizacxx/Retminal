@echo off
title Construction de Retminal
echo ============================================
echo    Construction de Retminal (rapide, --onedir)
echo ============================================
echo.

echo Verification des modules necessaires...
pip install pyinstaller paramiko pillow cryptography
echo.

REM --onedir = lancement QUASI INSTANTANE (avant, --onefile decompressait
REM tout dans un dossier temporaire a CHAQUE lancement -> ~10 secondes).
pyinstaller --noconfirm --onedir --noconsole --name Retminal --icon "Retminal.ico" --add-data "Retminal.ico;." --add-data "Retminal_icone.png;." retminal.py

echo.
echo Mets ton fichier secret.env dans le dossier  dist\Retminal\  (a cote de Retminal.exe) !
echo.
echo ============================================
echo    Termine !
echo    Ton appli = le DOSSIER  dist\Retminal\
echo    Lance  dist\Retminal\Retminal.exe  (fais un raccourci sur le Bureau)
echo    -^> Demarrage quasi instantane (avant : ~10s avec --onefile)
echo ============================================
pause
