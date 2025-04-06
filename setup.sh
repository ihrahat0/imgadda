#!/bin/bash

# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate

# Update pip first
pip install --upgrade pip

# Clean any previous installations
pip cache purge

# Install dependencies with no cache
pip install --no-cache-dir -r requirements.txt

echo "Setup complete! Run 'python image_merger_bot.py' to start the bot." 