@echo off
REM Build FolderCheck.exe on Windows.
REM
REM Requirements: Python 3.10+ from python.org (Tk is included).
REM Run from this folder in cmd.exe or PowerShell.

setlocal
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set PY=py -3
) else (
    set PY=python
)

echo == Installing/upgrading build deps ==
%PY% -m pip install --upgrade pip pyinstaller pillow || goto :fail

echo == Regenerating icon ==
%PY% build_icon.py || goto :fail

echo == Cleaning previous build ==
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist FolderCheck.spec del /q FolderCheck.spec

echo == Building FolderCheck.exe ==
%PY% -m PyInstaller ^
    --noconfirm ^
    --windowed ^
    --onefile ^
    --name FolderCheck ^
    --icon icon\FolderCheck.ico ^
    foldercheck.py || goto :fail

echo.
echo Done. Executable: dist\FolderCheck.exe
exit /b 0

:fail
echo BUILD FAILED
exit /b 1
