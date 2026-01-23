#!/bin/bash
# Setup script for AI Trading Bot Platform

echo "========================================="
echo "AI Trading Bot Platform Setup"
echo "========================================="

# Check Python version
python_version=$(python --version 2>&1 | grep -Po '(?<=Python )(.+)')
if [[ -z "$python_version" ]]; then
    echo "Error: Python is not installed"
    exit 1
fi

echo "Python version: $python_version"

# Create virtual environment
echo "Creating virtual environment..."
python -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p logs
mkdir -p models
mkdir -p data

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# Environment variables for AI Trading Bot
# Add your API keys and configuration here

# Example:
# API_KEY=your_api_key_here
# API_SECRET=your_api_secret_here
EOF
fi

echo ""
echo "========================================="
echo "Setup completed successfully!"
echo "========================================="
echo ""
echo "To get started:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Review and update config.yaml"
echo "3. Run the bot: python main.py --train --cycles 1"
echo "4. Or start the dashboard: python main.py --dashboard"
echo ""
