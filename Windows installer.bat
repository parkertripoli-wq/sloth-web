@echo off

winget install -e --id Python.Python.3.13.7

python -m ensurepip --upgrade
python -m pip install --upgrade pip

setlocal EnableDelayedExpansion

:: Set installation directory to user profile
set "INSTALL_DIR=%USERPROFILE%\SlothWeb\bwsr"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
cd /d "%INSTALL_DIR%"

echo Checking for Python...
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python not found. Downloading Python 3.13.7...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.13.7/python-3.13.7-amd64.exe' -OutFile 'python-3.13.7-amd64.exe'"
    echo Please run 'python-3.13.7-amd64.exe' now, and ensure to check "Add Python to PATH" during installation.
    echo After installation, press any key to continue...
    pause
    where python >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        echo Python installation failed or not added to PATH. Please install manually and retry.
        pause
        exit /b 1
    )
)

echo Downloading the icon (sloth_web.ico)...
powershell -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/refs/heads/main/sloth_web.ico' -OutFile 'sloth_web.ico'"

echo Downloading the browser (bwsr.py)...
powershell -Command "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/parkertripoli-wq/sloth-web/refs/heads/main/bwsr.py' -OutFile 'bwsr.py'"

echo Installing dependencies...
python -m pip install PyQt5 PyQtWebEngine requests || (
    echo Failed to install dependencies. Ensure pip is installed and you have internet access.
    echo Run 'python -m ensurepip --upgrade' and 'python -m pip install --upgrade pip' if needed.
    pause
    exit /b 1
)

echo Creating shortcuts...
echo Set oWS = WScript.CreateObject("WScript.Shell") > CreateShortcut.vbs
echo sLinkFile = "%USERPROFILE%\Desktop\Sloth Web Browser.lnk" >> CreateShortcut.vbs
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> CreateShortcut.vbs
echo oLink.TargetPath = "%INSTALL_DIR%\bwsr.py" >> CreateShortcut.vbs
echo oLink.WorkingDirectory = "%INSTALL_DIR%" >> CreateShortcut.vbs
echo oLink.IconLocation = "%INSTALL_DIR%\sloth_web.ico" >> CreateShortcut.vbs
echo oLink.Save >> CreateShortcut.vbs
cscript CreateShortcut.vbs
del CreateShortcut.vbs

echo Set oWS = WScript.CreateObject("WScript.Shell") > CreateShortcut.vbs
echo sLinkFile = "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Sloth Web Browser.lnk" >> CreateShortcut.vbs
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> CreateShortcut.vbs
echo oLink.TargetPath = "%INSTALL_DIR%\bwsr.py" >> CreateShortcut.vbs
echo oLink.WorkingDirectory = "%INSTALL_DIR%" >> CreateShortcut.vbs
echo oLink.IconLocation = "%INSTALL_DIR%\sloth_web.ico" >> CreateShortcut.vbs
echo oLink.Save >> CreateShortcut.vbs
cscript CreateShortcut.vbs
del CreateShortcut.vbs

echo Installation complete! Shortcuts are on your Desktop and Start Menu.
echo Visit https://parkertripoli-wq.github.io/ to browse and install extensions for Sloth Web. (work in progress)
echo Run Sloth Web Browser by double-clicking the shortcut or typing 'python bwsr.py' in %INSTALL_DIR%.
echo bye have a nice day!
pause
