@echo off
rem Starts volcano_server.py in the background (no console window).
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" /D "%~dp0" pyw "%~dp0volcano_server.py"
) else (
    start "" /D "%~dp0" pythonw "%~dp0volcano_server.py"
)