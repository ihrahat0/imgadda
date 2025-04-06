#!/bin/bash

echo "Installing required dependencies..."
pip install python-telegram-bot Pillow

echo "Starting fixed merger bot..."
python fixed_merger_bot.py