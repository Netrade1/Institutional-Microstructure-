@echo off
REM Setup script for AI Trading Bot Platform (Windows)

echo =========================================
echo AI Trading Bot Platform Setup
echo =========================================

REM Check Python version
python --version
if errorlevel 1 (
    echo Error: Python is not installed
    exit /b 1
)

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo Installing dependencies...
pip install -r requirements.txt

REM Create necessary directories
echo Creating directories...
if not exist logs mkdir logs
if not exist models mkdir models
if not exist data mkdir data

REM Create .env file if it doesn't exist
if not exist .env (
    echo Creating .env file...
    (
        echo # Environment variables for AI Trading Bot
        echo # Add your API keys and configuration here
        echo.
        echo # Example:
        echo # API_KEY=your_api_key_here
        echo # API_SECRET=your_api_secret_here
    ) > .env
)

echo.
echo =========================================
echo Setup completed successfully!
echo =========================================
echo.
echo To get started:
echo 1. Activate the virtual environment: venv\Scripts\activate.bat
echo 2. Review and update config.yaml
echo 3. Run the bot: python main.py --train --cycles 1
echo 4. Or start the dashboard: python main.py --dashboard
echo.

pause
