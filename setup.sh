#!/bin/bash
# Setup script for whisper-server

echo "Setting up whisper-server..."

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "Installing ffmpeg..."
    brew install ffmpeg
else
    echo "ffmpeg is already installed"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip and build tools
echo "Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

# Install Cython first (helps with av compilation)
echo "Installing Cython..."
pip install Cython

# Set environment variables to help with av compilation
export PKG_CONFIG_PATH="/opt/homebrew/lib/pkgconfig:$PKG_CONFIG_PATH"
export LDFLAGS="-L/opt/homebrew/lib"
export CPPFLAGS="-I/opt/homebrew/include"

# Install requirements
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Setup complete! To activate the virtual environment, run: source venv/bin/activate"




