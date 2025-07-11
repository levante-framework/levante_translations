@echo off
echo Deploying Levante Audio Dashboard to Vercel...
echo.

REM Deploy to production
echo [1/3] Deploying to production...
vercel --prod

REM Check if deployment was successful
if %errorlevel% neq 0 (
    echo ERROR: Deployment failed!
    pause
    exit /b 1
)

REM Get the latest deployment URL
echo.
echo [2/3] Getting latest deployment URL...
for /f "tokens=2 delims= " %%a in ('vercel ls --limit 1') do set LATEST_URL=%%a

REM Set up aliases
echo.
echo [3/3] Setting up aliases...
vercel alias set %LATEST_URL% audio-dashboard-levante.vercel.app
vercel alias set %LATEST_URL% levante-audio-dashboard.vercel.app

echo.
echo ✅ Deployment complete!
echo.
echo 🌐 Your dashboard is now available at:
echo   • https://audio-dashboard-levante.vercel.app
echo   • https://levante-audio-dashboard.vercel.app
echo   • %LATEST_URL%
echo.
pause 