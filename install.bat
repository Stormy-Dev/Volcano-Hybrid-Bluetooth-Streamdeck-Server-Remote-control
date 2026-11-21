@echo off
setlocal
cd /d "%~dp0"
title Volcano Remote setup

rem Python versions with Windows wheels for all dependencies, in order of preference.
rem storzandbickel_ble needs 3.14 or newer.
set "ACCEPTED=3.14 3.15"
rem Version installed if none of the above is present.
set "INSTALL_VERSION=3.14"

echo Volcano Remote setup
echo.

rem Reuse an existing virtual environment if it still works.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys" >nul 2>nul && goto deps
    echo The existing .venv is broken, recreating it ...
    rmdir /s /q ".venv"
)

call :find_python
if not defined PY call :install_python
if not defined PY (
    echo.
    echo Python could not be installed automatically.
    echo Please install Python %INSTALL_VERSION% from https://www.python.org/downloads/
    echo and run this file again.
    goto fail
)

echo Creating virtual environment with Python %PYVER% ...
py -%PYVER% -m venv ".venv" || goto fail

:deps
echo Installing dependencies ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt || goto fail

echo.
echo Setup complete. Starting the server ...
call volcano_start.bat
echo.
echo Next step: double-click stream-deck\VolcanoRemote.streamDeckAction to import the buttons.
echo.
pause
exit /b 0

:fail
echo.
echo Setup failed. See the messages above.
pause
exit /b 1

rem ---------------------------------------------------------------------------
:find_python
set "PY="
set "PYVER="
where py >nul 2>nul || exit /b 0
for %%V in (%ACCEPTED%) do if not defined PY (
    py -%%V -c "import sys" >nul 2>nul && (set "PY=1" & set "PYVER=%%V")
)
exit /b 0

:install_python
where py >nul 2>nul
if errorlevel 1 (
    where winget >nul 2>nul || exit /b 0
    echo Installing the official Python install manager ...
    winget install --id 9NQ7512CXL7T --source msstore --accept-package-agreements --accept-source-agreements
)
echo Installing Python %INSTALL_VERSION% ...
py install %INSTALL_VERSION%
call :find_python
exit /b 0
