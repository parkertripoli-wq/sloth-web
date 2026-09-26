@echo off
setlocal EnableExtensions
title Sloth Web 3.0 installer
echo ========================================
echo   Sloth Web 3.0  —  Windows installer
echo ========================================
echo.

set "INSTALL_DIR=%USERPROFILE%\SlothWeb"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: ---- find a REAL python (ignore the Microsoft Store stub) ----
set "PY="
call :find_python
if defined PY (
    "%PY%" -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
    if errorlevel 1 set "PY="
)
if defined PY goto :have_python

echo Python 3.10+ is not installed. Installing Python 3.13 silently...
echo This can take a few minutes. Do not close this window.
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.7/python-3.13.7-amd64.exe' -OutFile '%TEMP%\sloth-python-setup.exe' -UseBasicParsing"
if not exist "%TEMP%\sloth-python-setup.exe" (
    echo Could not download Python. Check your internet and run this again.
    pause
    exit /b 1
)
"%TEMP%\sloth-python-setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0 SimpleInstall=1
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" set "PY=%LocalAppData%\Programs\Python\Python313\python.exe"
if not defined PY if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PY (
    echo Python installed but python.exe was not found.
    echo Open a NEW Command Prompt and run this installer again.
    pause
    exit /b 1
)

:have_python
echo Using: %PY%
"%PY%" --version
if errorlevel 1 (
    echo That Python does not run. Re-run this installer.
    pause
    exit /b 1
)

:: ---- private environment so modules always install ----
echo.
echo Creating a private Python environment...
if not exist "%INSTALL_DIR%\venv\Scripts\python.exe" (
    "%PY%" -m venv "%INSTALL_DIR%\venv"
)
if not exist "%INSTALL_DIR%\venv\Scripts\python.exe" (
    echo venv failed, trying virtualenv...
    "%PY%" -m pip install --user virtualenv
    "%PY%" -m virtualenv "%INSTALL_DIR%\venv"
)
set "VPY=%INSTALL_DIR%\venv\Scripts\python.exe"
set "VPYW=%INSTALL_DIR%\venv\Scripts\pythonw.exe"
if not exist "%VPY%" (
    echo Could not create the Python environment.
    pause
    exit /b 1
)
if not exist "%VPYW%" set "VPYW=%VPY%"

echo Installing PyQt6, WebEngine, and requests...
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install PyQt6 PyQt6-WebEngine requests
if errorlevel 1 (
    echo.
    echo Module install failed. Retrying once...
    "%VPY%" -m pip install --upgrade pip
    "%VPY%" -m pip install PyQt6 PyQt6-WebEngine requests
)
"%VPY%" -c "import PyQt6, PyQt6.QtWebEngineWidgets, requests; print('modules ok')"
if errorlevel 1 (
    echo.
    echo Python modules did not install. Scroll up for the pip error.
    pause
    exit /b 1
)
"%VPY%" -m pip install pywin32 win10toast >nul 2>&1

:: ---- browser file: next to this installer, Downloads, then GitHub ----
echo.
echo Looking for Sloth Web...
set "GOT="
if exist "%~dp0SlothWeb-3.0.py" copy /y "%~dp0SlothWeb-3.0.py" "%INSTALL_DIR%\SlothWeb.py" >nul && set "GOT=1"
if not defined GOT if exist "%~dp0SlothWeb.py" copy /y "%~dp0SlothWeb.py" "%INSTALL_DIR%\SlothWeb.py" >nul && set "GOT=1"
if not defined GOT if exist "%USERPROFILE%\Downloads\SlothWeb-3.0.py" copy /y "%USERPROFILE%\Downloads\SlothWeb-3.0.py" "%INSTALL_DIR%\SlothWeb.py" >nul && set "GOT=1"
if not defined GOT (
    echo Downloading from GitHub...
    powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue'; $u=@('https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/main/SlothWeb-3.0.py','https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/main/bwsr.py'); foreach($x in $u){ try { Invoke-WebRequest -Uri $x -OutFile '%INSTALL_DIR%\SlothWeb.py' -UseBasicParsing; if((Get-Item '%INSTALL_DIR%\SlothWeb.py').Length -gt 10000){ exit 0 } } catch {} }; exit 1"
    if not errorlevel 1 set "GOT=1"
)
if not defined GOT (
    echo Could not find SlothWeb-3.0.py.
    echo Put SlothWeb-3.0.py in the same folder as this installer and run it again.
    pause
    exit /b 1
)
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/main/sloth_web.ico' -OutFile '%INSTALL_DIR%\sloth_web.ico' -UseBasicParsing } catch { }" >nul 2>&1

:: launcher the shortcut actually runs
> "%INSTALL_DIR%\launch-slothweb.bat" echo @echo off
>> "%INSTALL_DIR%\launch-slothweb.bat" echo cd /d "%INSTALL_DIR%"
>> "%INSTALL_DIR%\launch-slothweb.bat" echo "%VPYW%" "%INSTALL_DIR%\SlothWeb.py"
>> "%INSTALL_DIR%\launch-slothweb.bat" echo if errorlevel 1 pause

:: ---- desktop + start menu, including OneDrive desktops ----
echo.
echo Creating desktop shortcut...
set "ICON=%INSTALL_DIR%\sloth_web.ico"
if not exist "%ICON%" set "ICON=%VPYW%,0"

set "MADE=0"
for %%D in ("%USERPROFILE%\Desktop" "%USERPROFILE%\OneDrive\Desktop" "%USERPROFILE%\OneDrive - Personal\Desktop" "%PUBLIC%\Desktop") do (
    if exist "%%~D" call :shortcut "%%~D\Sloth Web.lnk"
)
if exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs" call :shortcut "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Sloth Web.lnk"

echo.
echo ========================================
echo   Python:   %PY%
echo   Modules:  installed in %INSTALL_DIR%\venv
echo   Browser:  %INSTALL_DIR%\SlothWeb.py
if "%MADE%"=="0" (
    echo   Shortcut failed. Run:  "%INSTALL_DIR%\launch-slothweb.bat"
) else (
    echo   Shortcut: Desktop \ Sloth Web
)
echo ========================================
pause
exit /b 0

:find_python
set "PY="
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
    set "PY=%LocalAppData%\Programs\Python\Python313\python.exe"
    exit /b 0
)
if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
    set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
    exit /b 0
)
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    set "PY=%LocalAppData%\Programs\Python\Python311\python.exe"
    exit /b 0
)
for /f "delims=" %%I in ('where python 2^>nul') do (
    echo %%I | find /i "WindowsApps" >nul
    if errorlevel 1 (
        set "PY=%%I"
        exit /b 0
    )
)
exit /b 0

:shortcut
set "LNK=%~1"
> "%TEMP%\sloth_sc.vbs" echo Set ws = CreateObject("WScript.Shell")
>> "%TEMP%\sloth_sc.vbs" echo Set s = ws.CreateShortcut("%LNK%")
>> "%TEMP%\sloth_sc.vbs" echo s.TargetPath = "%VPYW%"
>> "%TEMP%\sloth_sc.vbs" echo s.Arguments = "%INSTALL_DIR%\SlothWeb.py"
>> "%TEMP%\sloth_sc.vbs" echo s.WorkingDirectory = "%INSTALL_DIR%"
>> "%TEMP%\sloth_sc.vbs" echo s.IconLocation = "%ICON%"
>> "%TEMP%\sloth_sc.vbs" echo s.WindowStyle = 7
>> "%TEMP%\sloth_sc.vbs" echo s.Description = "Sloth Web"
>> "%TEMP%\sloth_sc.vbs" echo s.Save
cscript //nologo "%TEMP%\sloth_sc.vbs"
if exist "%LNK%" (
    echo   wrote %LNK%
    set "MADE=1"
) else (
    echo   could not write %LNK%
)
del "%TEMP%\sloth_sc.vbs" >nul 2>&1
exit /b 0
