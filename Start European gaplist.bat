@echo off
rem Double-click this file (Windows) to open the European gaplist notebook.
rem Keep the window open while you work; close it when done.
cd /d "%~dp0"
where pixi >nul 2>nul || (echo pixi is not installed yet. See docs\getting-started.md, "One-time setup". & pause & exit /b 1)
echo Starting the European gaplist notebook. It opens in your web browser.
pixi run lab
pause
