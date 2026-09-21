@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Sloth Web 3.0 installer
echo ========================================
echo   Sloth Web 3.0  —  Windows installer
echo ========================================
echo.

set "INSTALL_DIR=%USERPROFILE%\SlothWeb"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
cd /d "%INSTALL_DIR%"

where python >nul 2>&1
if errorlevel 1 (
    echo Installing Python with winget...
    winget install -e --id Python.Python.3.13 --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo winget could not install Python. Downloading the official installer...
        powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.7/python-3.13.7-amd64.exe' -OutFile '%TEMP%\python-setup.exe'"
        echo.
        echo A Python installer window will open.
        echo CHECK "Add python.exe to PATH" then click Install Now.
        start /wait "" "%TEMP%\python-setup.exe"
    )
    echo Refreshing PATH...
    set "PATH=%LocalAppData%\Programs\Python\Python313;%LocalAppData%\Programs\Python\Python313\Scripts;%ProgramFiles%\Python313;%PATH%"
)

where python >nul 2>&1
if errorlevel 1 (
    echo Python is still not on PATH. Close this window, open a NEW Command Prompt, and run this installer again.
    pause
    exit /b 1
)

python --version
python -m ensurepip --upgrade >nul 2>&1
python -m pip install --upgrade pip
echo Installing PyQt6 (this can take a minute)...
python -m pip install PyQt6 PyQt6-WebEngine requests
python -m pip install pywin32 win10toast >nul 2>&1

set "REPO=https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/main"
echo Downloading Sloth Web...
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%REPO%/SlothWeb-3.0.py' -OutFile 'SlothWeb.py' -UseBasicParsing } catch { Invoke-WebRequest -Uri '%REPO%/bwsr.py' -OutFile 'SlothWeb.py' -UseBasicParsing }"
if not exist "SlothWeb.py" (
    echo Download failed. Check your internet and try again.
    pause
    exit /b 1
)
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%REPO%/sloth_web.ico' -OutFile 'sloth_web.ico' -UseBasicParsing } catch { }"

:: Launcher so the shortcut never opens in Notepad
echo @echo off> "%INSTALL_DIR%\launch-slothweb.bat"
echo cd /d "%INSTALL_DIR%">> "%INSTALL_DIR%\launch-slothweb.bat"
echo python "%INSTALL_DIR%\SlothWeb.py">> "%INSTALL_DIR%\launch-slothweb.bat"
echo if errorlevel 1 pause>> "%INSTALL_DIR%\launch-slothweb.bat"

for /f "delims=" %%I in ('where python') do (
    set "PYEXE=%%I"
    goto :gotpy
)
:gotpy
set "PYW=%PYEXE:python.exe=pythonw.exe%"
if not exist "%PYW%" set "PYW=%PYEXE%"

echo Creating Desktop and Start Menu shortcuts...
echo Set oWS = WScript.CreateObject("WScript.Shell") > "%TEMP%\sloth_shortcut.vbs"
echo Set oLink = oWS.CreateShortcut("%USERPROFILE%\Desktop\Sloth Web.lnk") >> "%TEMP%\sloth_shortcut.vbs"
echo oLink.TargetPath = "%PYW%" >> "%TEMP%\sloth_shortcut.vbs"
echo oLink.Arguments = chr(34^) ^& "%INSTALL_DIR%\SlothWeb.py" ^& chr(34^) >> "%TEMP%\sloth_shortcut.vbs"
echo oLink.WorkingDirectory = "%INSTALL_DIR%" >> "%TEMP%\sloth_shortcut.vbs"
echo oLink.IconLocation = "%INSTALL_DIR%\sloth_web.ico" >> "%TEMP%\sloth_shortcut.vbs"
echo oLink.Save >> "%TEMP%\sloth_shortcut.vbs"
echo Set oLink = oWS.CreateShortcut("%APPDATA%\Microsoft\Windows\Start Menu\Programs\Sloth Web.lnk") >> "%TEMP%\sloth_shortcut.vbs"
echo oLink.TargetPath = "%PYW%" >> "%TEMP%\sloth_shortcut.vbs"
echo oLink.Arguments = chr(34^) ^& "%INSTALL_DIR%\SlothWeb.py" ^& chr(34^) >> "%TEMP%\sloth_shortcut.vbs"
echo oLink.WorkingDirectory = "%INSTALL_DIR%" >> "%TEMP%\sloth_shortcut.vbs"
echo oLink.IconLocation = "%INSTALL_DIR%\sloth_web.ico" >> "%TEMP%\sloth_shortcut.vbs"
echo oLink.Save >> "%TEMP%\sloth_shortcut.vbs"
cscript //nologo "%TEMP%\sloth_shortcut.vbs"
del "%TEMP%\sloth_shortcut.vbs" >nul 2>&1

echo.
echo ========================================
echo   Installed to: %INSTALL_DIR%
echo   Shortcut:     Desktop \ Sloth Web
echo   Or run:       python "%INSTALL_DIR%\SlothWeb.py"
echo ========================================
pause
