#!/bin/bash

# Check if virtual environment exists and activate it
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the bot
python image_merger_bot.py 