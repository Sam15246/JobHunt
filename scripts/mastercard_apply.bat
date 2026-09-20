@echo off
REM -------------------------------------------------------
REM  Mastercard Pipeline - Apply (headed browser)
REM  Schedule: once daily on weekdays (e.g. 10AM)
REM  NOTE: This opens a browser window. Run when you're at
REM  your PC so you can monitor the first few runs.
REM -------------------------------------------------------

cd /d C:\Dev\JobHunt

echo ===== %date% %time% - Mastercard Apply ===== >> logs\mastercard.log 2>&1

python main.py apply --platform workday --employer mastercard --limit 5 >> logs\mastercard.log 2>&1

echo [Apply done] Checking review queue... >> logs\mastercard.log 2>&1
python main.py review-queue >> logs\mastercard.log 2>&1

python main.py stats >> logs\mastercard.log 2>&1

echo ===== Apply Done ===== >> logs\mastercard.log 2>&1
echo. >> logs\mastercard.log 2>&1
