@echo off
setlocal

set VENV_DIR=.venv
set SCRIPT_DIR=%~dp0

if not exist "%SCRIPT_DIR%%VENV_DIR%\Scripts\activate.bat" (
    echo Virtual environment not found in %SCRIPT_DIR%%VENV_DIR%.
    echo Please run setup.bat first.
    goto :eof
)

call "%SCRIPT_DIR%%VENV_DIR%\Scripts\activate.bat"

echo Launching WIPT GUI...
python "%SCRIPT_DIR%wipt_gui.py"

endlocal
