@echo off
REM -------------------------------------------------------
REM  Mastercard Pipeline - Scrape + Filter + Score + Route
REM  Schedule: every 8 hours on weekdays (e.g. 8AM, 4PM)
REM -------------------------------------------------------

cd /d C:\Dev\JobHunt

echo ===== %date% %time% - Mastercard Scrape Pipeline ===== >> logs\mastercard.log 2>&1

echo [1/5] Scraping Workday... >> logs\mastercard.log 2>&1
python main.py scrape --source workday --employer mastercard >> logs\mastercard.log 2>&1

echo [2/5] Keyword filter... >> logs\mastercard.log 2>&1
python main.py filter >> logs\mastercard.log 2>&1

echo [3/5] AI scoring... >> logs\mastercard.log 2>&1
python main.py score >> logs\mastercard.log 2>&1

echo [4/5] Resume routing... >> logs\mastercard.log 2>&1
python main.py assign-resumes >> logs\mastercard.log 2>&1

echo [5/5] Stats... >> logs\mastercard.log 2>&1
python main.py stats >> logs\mastercard.log 2>&1

echo ===== Done ===== >> logs\mastercard.log 2>&1
echo. >> logs\mastercard.log 2>&1
