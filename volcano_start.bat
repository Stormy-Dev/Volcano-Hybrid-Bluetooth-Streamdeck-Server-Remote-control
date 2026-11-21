@echo off
rem Starts volcano_server.py in the background (no console window).
set "HERE=%~dp0"
if exist "%HERE%.venv\Scripts\pythonw.exe" (
    start "" /D "%HERE%" "%HERE%.venv\Scripts\pythonw.exe" "%HERE%volcano_server.py"
    exit /b 0
)
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" /D "%HERE%" pyw "%HERE%volcano_server.py"
) else (
    start "" /D "%HERE%" pythonw "%HERE%volcano_server.py"
)
