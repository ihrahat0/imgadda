# Image Merger Telegram Bot

A Telegram bot that merges two images by placing a reference image (60x60 pixels) in the center of a main image and adds a user-specified name at the bottom.

## Features

- Accepts two images from the user
- Places the second image in the center of the first image (60x60 pixels)
- Adds the user's name at the bottom center of the image
- Sends back the combined image

## Setup

### Option 1: Using the setup script (recommended)

1. Run the setup script:

```bash
./setup.sh
```

This will:
- Create a virtual environment
- Install all dependencies

2. If using a virtual environment, activate it:

```bash
source venv/bin/activate
```

### Option 2: Manual installation

1. It's recommended to use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

2. Install the dependencies:

```bash
pip install -r requirements.txt
```

## Running the Bot

### Option 1: Run script (recommended)

```bash
./run.sh
```

### Option 2: Manual run

The bot token is already included in the code, but for better security, you can set it as an environment variable:

```bash
export TELEGRAM_TOKEN="8125048019:AAHSoPTvoybOkwtCLvWO_4I_PXNthWpqEtM"
python fixed_merger_bot.py
```

## Usage

1. Start a chat with your bot on Telegram
2. Send the `/start` command to begin
3. Follow these steps:
   - Send the main image (background)
   - Send the reference image (to be placed in the center)
   - Send the name you want to appear at the bottom
4. The bot will process your images and send back the combined result

## Cancel Operation

At any time, you can send `/cancel` to stop the current operation.

## Technical Notes

- This bot uses the latest python-telegram-bot (v20+) which uses async/await syntax
- It supports older versions of Pillow with fallbacks for text width calculations
- The image processing is done using the Pillow library

## Security Notes

- For production use, never hardcode the bot token in your code
- Consider using environment variables or a .env file for sensitive information
- The current implementation stores images in memory, which is suitable for small-scale use

## Troubleshooting

If you encounter dependency issues:
1. Make sure you're using the correct version of urllib3 (1.26.15)
2. Try installing in a fresh virtual environment
3. Check for any conflicting global packages 