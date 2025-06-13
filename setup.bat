@echo off
setlocal

echo Checking for Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not found in PATH.
    echo Please install Python 3.10+ and ensure it's added to your PATH.
    goto :eof
) else (
    echo Python found.
)

set VENV_DIR=.venv
if not exist "%VENV_DIR%\Scripts\activate.bat" (
    echo Creating virtual environment in %VENV_DIR%...
    python -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment.
        goto :eof
    )
    echo Virtual environment created.
) else (
    echo Virtual environment %VENV_DIR% already exists.
)

echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if defined VIRTUAL_ENV (
    echo Virtual environment activated.
) else (
    echo ERROR: Failed to activate virtual environment.
    echo Please check your Python installation and venv setup.
    goto :eof
)

echo Installing dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    echo Please check requirements.txt and your internet connection.
    goto :eof
)
echo Dependencies installed successfully.

echo Running WIPT setup script (setup.py) to fetch assets...
python setup.py
if %errorlevel% neq 0 (
    echo WARNING: setup.py encountered errors. Some assets might be missing.
    echo Please check the output above for details.
) else (
    echo setup.py completed.
)

echo.
echo WIPT setup process finished.
echo To run WIPT, use the run_wipt.bat script (e.g., run_wipt.bat patch --input ...).

endlocal
goto :eof

:eof
exit /b %errorlevel%
