@echo off
setlocal

set VENV_DIR=.venv
set WIPT_SCRIPT=wipt.py

if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo ERROR: Virtual environment %VENV_DIR% not found.
    echo Please run setup.bat first to create the environment and install dependencies.
    goto :eof
)

if not exist "%WIPT_SCRIPT%" (
    echo ERROR: WIPT script (%WIPT_SCRIPT%) not found in the current directory.
    echo Ensure you are in the correct WIPT project directory.
    goto :eof
)

REM Activate the virtual environment
call "%VENV_DIR%\Scripts\activate.bat"
if not defined VIRTUAL_ENV (
    echo ERROR: Failed to activate virtual environment.
    goto :eof
)

REM Run the wipt.py script with all arguments passed to this batch file
echo Running WIPT: python %WIPT_SCRIPT% %*
python %WIPT_SCRIPT% %*

endlocal
goto :eof

:eof
exit /b %errorlevel%
