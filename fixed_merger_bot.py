import os
import logging
import requests
import tempfile
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
FIRST_IMAGE, SECOND_IMAGE, NAME, SETTINGS, CUSTOM_SPACING, SPACING_INPUT, PRESETS, SAVE_PRESET, LOAD_PRESET, PRESET_NAME, DELETE_PRESET, EDIT_PRESET = range(12)

# Store user data
user_data = {}

# Config parameters
REF_IMAGE_SIZE = 400  # Size of reference image (400x400 pixels)
FONT_SIZE = 48  # Font size
BOTTOM_MARGIN = 10  # Margin from bottom in pixels

# Font URL for Boldonse
BOLDONSE_FONT_URL = "https://fonts.googleapis.com/css2?family=Boldonse&display=swap"
FONT_FILE_PATH = "boldonse.ttf"

# Default spacing values - now it's offsets from center with 0,0 being center
DEFAULT_SPACING = {
    "image_x": 0,
    "image_y": 0,
    "text_x": 0,
    "text_y": 0
}

# Preset file path
PRESETS_FILE = "spacing_presets.json"

# Channel/Group IDs
GROUP_CHAT_ID = "allimarged"  # Target group to send merged images to

# Define spacing keys
SPACING_KEYS = ["image_x", "image_y", "text_x", "text_y"]

# Command texts (for reply keyboards)
CREATE_IMAGE_TEXT = "🖼️ Create New Image"
SETTINGS_TEXT = "⚙️ Settings"
CANCEL_TEXT = "❌ Cancel"
BACK_TEXT = "⬅️ Back"
CUSTOM_SPACING_TEXT = "📏 Position Settings"
PRESETS_TEXT = "💾 Presets"
SAVE_PRESET_TEXT = "💾 Save as Preset"
DONE_TEXT = "✅ Done"
DELETE_PRESET_TEXT = "🗑️ Delete Preset"
EDIT_PRESET_TEXT = "✏️ Edit Preset"
# Direction selection texts
IMAGE_X_TEXT = "◀️ Move Image Left/Right ▶️"
IMAGE_Y_TEXT = "🔼 Move Image Up/Down 🔽"
TEXT_X_TEXT = "◀️ Move Text Left/Right ▶️"
TEXT_Y_TEXT = "🔼 Move Text Up/Down 🔽"

def load_presets():
    """Load saved presets from file"""
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, 'r') as f:
                presets = json.load(f)
                # Migrate old preset format if needed
                migrated = False
                for preset_name, preset_data in presets.items():
                    if "spacing" in preset_data:
                        spacing = preset_data["spacing"]
                        # Check if using old format (has 'top', 'right', etc. but not 'image_x')
                        if "top" in spacing and "image_x" not in spacing:
                            # Convert old format to new format
                            preset_data["spacing"] = {
                                "image_x": 0,  # Default to center
                                "image_y": 0,  # Default to center
                                "text_x": 0,   # Default to center
                                "text_y": 0    # Default position
                            }
                            migrated = True
                
                # Save migrated presets if needed
                if migrated:
                    try:
                        with open(PRESETS_FILE, 'w') as f:
                            json.dump(presets, f)
                        logger.info("Migrated old preset format to new format")
                    except Exception as e:
                        logger.error(f"Error saving migrated presets: {e}")
                
                return presets
        except Exception as e:
            logger.error(f"Error loading presets: {e}")
    return {}

def save_presets(presets):
    """Save presets to file"""
    try:
        with open(PRESETS_FILE, 'w') as f:
            json.dump(presets, f)
        return True
    except Exception as e:
        logger.error(f"Error saving presets: {e}")
        return False

def download_font():
    """Download and save the Boldonse font from Google Fonts"""
    try:
        # Check if font already exists
        if os.path.exists(FONT_FILE_PATH):
            return True
            
        # First, get the CSS file
        css_response = requests.get(BOLDONSE_FONT_URL)
        if not css_response.ok:
            logger.error(f"Failed to fetch font CSS: {css_response.status_code}")
            return False
            
        # Extract the actual font URL from the CSS
        css_content = css_response.text
        font_url = None
        for line in css_content.split('\n'):
            if 'url(' in line and '.ttf' in line:
                start = line.find('url(') + 4
                end = line.find(')', start)
                font_url = line[start:end].strip().strip("'").strip('"')
                break
                
        if not font_url:
            logger.error("Could not find font URL in CSS")
            return False
            
        # Download the actual font file
        font_response = requests.get(font_url)
        if not font_response.ok:
            logger.error(f"Failed to download font file: {font_response.status_code}")
            return False
            
        # Save the font file
        with open(FONT_FILE_PATH, 'wb') as f:
            f.write(font_response.content)
            
        logger.info(f"Successfully downloaded Boldonse font to {FONT_FILE_PATH}")
        return True
    except Exception as e:
        logger.error(f"Error downloading font: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation."""
    keyboard = [
        [KeyboardButton(CREATE_IMAGE_TEXT)],
        [KeyboardButton(SETTINGS_TEXT)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Welcome! Use the buttons below to start creating an image or adjust settings.", 
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text commands from reply keyboard"""
    text = update.message.text
    
    if text == CREATE_IMAGE_TEXT:
        return await start_new_image(update, context)
    elif text == SETTINGS_TEXT:
        return await settings(update, context)
    elif text == BACK_TEXT:
        return await settings(update, context)
    elif text == CUSTOM_SPACING_TEXT:
        return await custom_spacing_menu(update, context)
    elif text == PRESETS_TEXT:
        return await presets_menu(update, context)
    elif text == SAVE_PRESET_TEXT:
        return await save_preset_prompt(update, context)
    elif text == DELETE_PRESET_TEXT:
        return await delete_preset_select(update, context)
    elif text == EDIT_PRESET_TEXT:
        return await edit_preset_select(update, context)
    elif text == DONE_TEXT:
        return await done_settings(update, context)
    elif text == CANCEL_TEXT:
        return await cancel(update, context)
    elif text.startswith("Preset:"):
        # Extract preset name from button text
        preset_name = text.replace("Preset:", "").strip()
        context.user_data["selected_preset"] = preset_name
        return await load_preset(update, context)
    
    return ConversationHandler.END

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display settings options"""
    user_id = update.message.from_user.id
    
    # Initialize user data if not exists
    if user_id not in user_data:
        user_data[user_id] = {}
    
    # Set default spacing if not already set
    if 'spacing' not in user_data[user_id]:
        user_data[user_id]['spacing'] = DEFAULT_SPACING.copy()
    
    # Create keyboard for settings
    spacing = user_data[user_id]['spacing']
    
    # Create position description with directional language
    image_pos = "Center"
    if spacing['image_x'] < 0:
        image_pos = f"{abs(spacing['image_x'])}px Left"
    elif spacing['image_x'] > 0:
        image_pos = f"{spacing['image_x']}px Right"
        
    if spacing['image_y'] != 0:
        if spacing['image_y'] < 0:
            image_pos += f", {abs(spacing['image_y'])}px Up"
        else:
            image_pos += f", {spacing['image_y']}px Down"
            
    text_pos = "Default"
    if spacing['text_x'] != 0 or spacing['text_y'] != 0:
        text_pos = ""
        if spacing['text_x'] < 0:
            text_pos = f"{abs(spacing['text_x'])}px Left"
        elif spacing['text_x'] > 0:
            text_pos = f"{spacing['text_x']}px Right"
            
        if spacing['text_y'] != 0:
            if text_pos:
                text_pos += ", "
            if spacing['text_y'] < 0:
                text_pos += f"{abs(spacing['text_y'])}px Up"
            else:
                text_pos += f"{spacing['text_y']}px Down"
    
    keyboard = [
        [KeyboardButton(f"{CUSTOM_SPACING_TEXT}")],
        [KeyboardButton(PRESETS_TEXT)],
        [KeyboardButton(DONE_TEXT)],
        [KeyboardButton(CREATE_IMAGE_TEXT)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Settings:\n\nImage position: {image_pos}\nText position: {text_pos}\n\n"
        f"Use the buttons below to adjust positions:",
        reply_markup=reply_markup
    )
    return SETTINGS

async def custom_spacing_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show custom spacing options"""
    user_id = update.message.from_user.id
    
    # Initialize user data if not exists
    if user_id not in user_data:
        user_data[user_id] = {}
    
    # Set default spacing if not already set
    if 'spacing' not in user_data[user_id]:
        user_data[user_id]['spacing'] = DEFAULT_SPACING.copy()
    
    spacing = user_data[user_id]['spacing']
    
    # Build keyboard with position options - with directional descriptions
    image_x_label = "Center"
    if spacing['image_x'] < 0:
        image_x_label = f"{abs(spacing['image_x'])}px Left"
    elif spacing['image_x'] > 0:
        image_x_label = f"{spacing['image_x']}px Right"
        
    image_y_label = "Center"
    if spacing['image_y'] < 0:
        image_y_label = f"{abs(spacing['image_y'])}px Up"
    elif spacing['image_y'] > 0:
        image_y_label = f"{spacing['image_y']}px Down"
        
    text_x_label = "Center"
    if spacing['text_x'] < 0:
        text_x_label = f"{abs(spacing['text_x'])}px Left"
    elif spacing['text_x'] > 0:
        text_x_label = f"{spacing['text_x']}px Right"
        
    text_y_label = "Default"
    if spacing['text_y'] < 0:
        text_y_label = f"{abs(spacing['text_y'])}px Up"
    elif spacing['text_y'] > 0:
        text_y_label = f"{spacing['text_y']}px Down"
    
    keyboard = [
        [KeyboardButton(f"{IMAGE_X_TEXT} ({image_x_label})")],
        [KeyboardButton(f"{IMAGE_Y_TEXT} ({image_y_label})")],
        [KeyboardButton(f"{TEXT_X_TEXT} ({text_x_label})")],
        [KeyboardButton(f"{TEXT_Y_TEXT} ({text_y_label})")],
        [KeyboardButton(BACK_TEXT)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Select which position to adjust:\n\n"
        f"The reference image is centered by default.\n"
        f"The text is positioned at the bottom center by default.",
        reply_markup=reply_markup
    )
    return CUSTOM_SPACING

async def handle_direction_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle selection of which position to edit"""
    text = update.message.text
    user_id = update.message.from_user.id
    
    # Check if user wants to go back
    if text == BACK_TEXT:
        return await settings(update, context)
    
    # Initialize spacing if not exists
    if user_id not in user_data:
        user_data[user_id] = {}
    if 'spacing' not in user_data[user_id]:
        user_data[user_id]['spacing'] = DEFAULT_SPACING.copy()
    
    # Determine which position was selected
    position_key = None
    if text.startswith(IMAGE_X_TEXT):
        position_key = "image_x"
        description = "Positive values move RIGHT, negative values move LEFT"
        current_value = user_data[user_id]['spacing'][position_key]
        current_text = "Centered horizontally"
        if current_value < 0:
            current_text = f"{abs(current_value)}px to the LEFT of center"
        elif current_value > 0:
            current_text = f"{current_value}px to the RIGHT of center"
    elif text.startswith(IMAGE_Y_TEXT):
        position_key = "image_y"
        description = "Positive values move DOWN, negative values move UP"
        current_value = user_data[user_id]['spacing'][position_key]
        current_text = "Centered vertically"
        if current_value < 0:
            current_text = f"{abs(current_value)}px ABOVE center"
        elif current_value > 0:
            current_text = f"{current_value}px BELOW center"
    elif text.startswith(TEXT_X_TEXT):
        position_key = "text_x"
        description = "Positive values move RIGHT, negative values move LEFT"
        current_value = user_data[user_id]['spacing'][position_key]
        current_text = "Centered horizontally"
        if current_value < 0:
            current_text = f"{abs(current_value)}px to the LEFT of center"
        elif current_value > 0:
            current_text = f"{current_value}px to the RIGHT of center"
    elif text.startswith(TEXT_Y_TEXT):
        position_key = "text_y"
        description = "Positive values move DOWN, negative values move UP"
        current_value = user_data[user_id]['spacing'][position_key]
        current_text = "Default position (near bottom)"
        if current_value < 0:
            current_text = f"{abs(current_value)}px HIGHER than default"
        elif current_value > 0:
            current_text = f"{current_value}px LOWER than default"
    
    if position_key:
        # Store the selected position key for later use
        user_data[user_id]['current_spacing_key'] = position_key
        
        # Ask for the value for this position
        keyboard = [
            [KeyboardButton(BACK_TEXT)]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"Current position: {current_text}\n\n"
            f"{description}\n\n"
            f"Enter a value in pixels (e.g. 50 or -50):",
            reply_markup=reply_markup
        )
        return SPACING_INPUT
    
    # If we didn't recognize the selection, go back to position selection
    return await custom_spacing_menu(update, context)

async def handle_spacing_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle position offset input"""
    user_id = update.message.from_user.id
    
    # Check if user wants to go back
    if update.message.text == BACK_TEXT:
        return await custom_spacing_menu(update, context)
    
    # Initialize user data if not exists
    if user_id not in user_data:
        user_data[user_id] = {}
        user_data[user_id]['spacing'] = DEFAULT_SPACING.copy()
    
    # Get the current key we're setting
    current_key = user_data[user_id].get('current_spacing_key', 'image_x')
    
    try:
        # Parse the value - now can be negative for offsets
        spacing_value = int(update.message.text.strip())
        
        # Update the spacing for the current key
        user_data[user_id]['spacing'][current_key] = spacing_value
        
        # Return to position selection menu
        return await custom_spacing_menu(update, context)
    
    except ValueError:
        # Invalid input
        keyboard = [
            [KeyboardButton(BACK_TEXT)]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"Please enter a valid number for {current_key} offset in pixels:",
            reply_markup=reply_markup
        )
        return SPACING_INPUT

async def presets_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show presets menu"""
    user_id = update.message.from_user.id
    
    # Load existing presets
    presets = load_presets()
    
    keyboard = []
    
    # Add buttons for each preset
    if presets:
        for preset_name, preset_data in presets.items():
            if "spacing" in preset_data:
                spacing = preset_data["spacing"]
                
                # Ensure spacing has all required keys with defaults
                if "image_x" not in spacing:
                    spacing["image_x"] = 0
                if "image_y" not in spacing:
                    spacing["image_y"] = 0
                if "text_x" not in spacing:
                    spacing["text_x"] = 0
                if "text_y" not in spacing:
                    spacing["text_y"] = 0
                
                # Create directional description for the preset
                image_pos = "Center"
                if spacing['image_x'] < 0:
                    image_pos = f"{abs(spacing['image_x'])}px Left"
                elif spacing['image_x'] > 0:
                    image_pos = f"{spacing['image_x']}px Right"
                    
                if spacing['image_y'] != 0:
                    if spacing['image_y'] < 0:
                        image_pos += f", {abs(spacing['image_y'])}px Up"
                    else:
                        image_pos += f", {spacing['image_y']}px Down"
                
                keyboard.append([
                    KeyboardButton(f"Preset: {preset_name} ({image_pos})")
                ])
    else:
        # No presets yet
        keyboard.append([KeyboardButton("No saved presets yet")])
    
    # Add save/edit/delete/back buttons
    keyboard.append([KeyboardButton(SAVE_PRESET_TEXT)])
    if presets:
        keyboard.append([KeyboardButton(EDIT_PRESET_TEXT)])
        keyboard.append([KeyboardButton(DELETE_PRESET_TEXT)])
    keyboard.append([KeyboardButton(BACK_TEXT)])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Position Presets:\nSelect a preset to load, or use the buttons below to manage presets.",
        reply_markup=reply_markup
    )
    return PRESETS

async def edit_preset_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show menu to select which preset to edit"""
    # Check if user wants to go back
    if update.message.text == BACK_TEXT:
        return await settings(update, context)
        
    # Load existing presets
    presets = load_presets()
    
    if not presets:
        await update.message.reply_text(
            "No presets found to edit.",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(BACK_TEXT)]
            ], resize_keyboard=True)
        )
        return PRESETS
    
    keyboard = []
    
    # Add buttons for each preset
    for preset_name, preset_data in presets.items():
        if "spacing" in preset_data:
            spacing = preset_data["spacing"]
            
            # Create directional description for the preset
            image_pos = "Center"
            if spacing.get('image_x', 0) < 0:
                image_pos = f"{abs(spacing.get('image_x', 0))}px Left"
            elif spacing.get('image_x', 0) > 0:
                image_pos = f"{spacing.get('image_x', 0)}px Right"
                
            if spacing.get('image_y', 0) != 0:
                if spacing.get('image_y', 0) < 0:
                    image_pos += f", {abs(spacing.get('image_y', 0))}px Up"
                else:
                    image_pos += f", {spacing.get('image_y', 0)}px Down"
                    
            keyboard.append([
                KeyboardButton(f"Edit: {preset_name} ({image_pos})")
            ])
    
    keyboard.append([KeyboardButton(BACK_TEXT)])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Select which preset you want to edit:",
        reply_markup=reply_markup
    )
    
    return EDIT_PRESET

async def edit_preset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle editing of a preset by loading its values and going to settings"""
    user_id = update.message.from_user.id
    
    # Check if user wants to go back
    if update.message.text == BACK_TEXT:
        return await presets_menu(update, context)
    
    # Extract preset name from text
    text = update.message.text
    if text.startswith("Edit:"):
        # Extract just the name part before any description in parentheses
        preset_name = text.replace("Edit:", "").split(" (")[0].strip()
        
        # Load presets
        presets = load_presets()
        
        if preset_name in presets:
            # Get preset data
            preset_data = presets[preset_name]
            
            # Initialize user data if not exists
            if user_id not in user_data:
                user_data[user_id] = {}
            
            # Load preset's spacing values into user data
            if 'spacing' in preset_data:
                spacing = preset_data["spacing"].copy()
                
                # Add any missing keys with defaults
                if "image_x" not in spacing:
                    spacing["image_x"] = 0
                if "image_y" not in spacing:
                    spacing["image_y"] = 0
                if "text_x" not in spacing:
                    spacing["text_x"] = 0
                if "text_y" not in spacing:
                    spacing["text_y"] = 0
                    
                user_data[user_id]['spacing'] = spacing
                
                # Store the preset name for later saving
                user_data[user_id]['editing_preset'] = preset_name
                
                # Go to custom spacing menu to edit values
                await update.message.reply_text(
                    f"Editing preset '{preset_name}'. Adjust the position values as needed, then save when done.",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton(CUSTOM_SPACING_TEXT)],
                        [KeyboardButton(SAVE_PRESET_TEXT)],
                        [KeyboardButton(BACK_TEXT)]
                    ], resize_keyboard=True)
                )
                return SETTINGS
            else:
                await update.message.reply_text(
                    "Error: Invalid preset data.",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton(BACK_TEXT)]
                    ], resize_keyboard=True)
                )
        else:
            await update.message.reply_text(
                "Error: Preset not found.",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton(BACK_TEXT)]
                ], resize_keyboard=True)
            )
    else:
        await update.message.reply_text(
            "Please select a preset to edit.",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(BACK_TEXT)]
            ], resize_keyboard=True)
        )
    
    return EDIT_PRESET

async def save_preset_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for preset name to save"""
    user_id = update.message.from_user.id
    
    # If we're editing an existing preset, prefill the name
    if user_id in user_data and 'editing_preset' in user_data[user_id]:
        preset_name = user_data[user_id]['editing_preset']
        await update.message.reply_text(
            f"You're editing preset '{preset_name}'.\nPressing save will update this preset. Type a different name to save as new preset:",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(preset_name)],  # Prefill the current name
                [KeyboardButton(BACK_TEXT)]
            ], resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            "Please enter a name for this preset:",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(BACK_TEXT)]
            ], resize_keyboard=True)
        )
    
    return PRESET_NAME

async def save_preset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save current spacing as a preset"""
    user_id = update.message.from_user.id
    
    # Check if user wants to go back
    if update.message.text == BACK_TEXT:
        return await settings(update, context)
        
    preset_name = update.message.text.strip()
    
    if not preset_name:
        await update.message.reply_text(
            "Preset name cannot be empty. Please try again:",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(BACK_TEXT)]
            ], resize_keyboard=True)
        )
        return PRESET_NAME
    
    # Get current spacing
    if user_id in user_data and 'spacing' in user_data[user_id]:
        spacing = user_data[user_id]['spacing']
        
        # Load existing presets
        presets = load_presets()
        
        # Add or update the preset
        presets[preset_name] = {
            "spacing": spacing
        }
        
        # Save presets
        if save_presets(presets):
            # Clear the editing flag if it exists
            if 'editing_preset' in user_data[user_id]:
                del user_data[user_id]['editing_preset']
            
            # Store the last used preset name
            user_data[user_id]['last_preset'] = preset_name
                
            await update.message.reply_text(
                f"Preset '{preset_name}' saved successfully!",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton(BACK_TEXT)]
                ], resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                "Error saving preset. Please try again.",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton(BACK_TEXT)]
                ], resize_keyboard=True)
            )
    else:
        await update.message.reply_text(
            "No spacing settings to save. Please configure spacing first.",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(BACK_TEXT)]
            ], resize_keyboard=True)
        )
    
    return SETTINGS

async def done_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to main menu after settings are done"""
    keyboard = [
        [KeyboardButton(CREATE_IMAGE_TEXT)],
        [KeyboardButton(SETTINGS_TEXT)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Settings saved! Use the buttons below to create an image.",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def start_new_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start creating a new image."""
    user_id = update.message.from_user.id
    
    # Check if user has a last preset to apply automatically
    last_preset_loaded = False
    if user_id in user_data and 'last_preset' in user_data[user_id]:
        last_preset = user_data[user_id]['last_preset']
        presets = load_presets()
        
        if last_preset in presets and 'spacing' in presets[last_preset]:
            # Apply the last preset automatically
            spacing = presets[last_preset]['spacing'].copy()
            
            # Ensure all keys exist
            if "image_x" not in spacing:
                spacing["image_x"] = 0
            if "image_y" not in spacing:
                spacing["image_y"] = 0
            if "text_x" not in spacing:
                spacing["text_x"] = 0
            if "text_y" not in spacing:
                spacing["text_y"] = 0
            
            # Update user's spacing with the preset
            if user_id not in user_data:
                user_data[user_id] = {}
            
            user_data[user_id]['spacing'] = spacing
            last_preset_loaded = True
    
    # Construct message based on whether preset was loaded
    message = "Great! Please send me the main image."
    if last_preset_loaded:
        # Create position description
        spacing = user_data[user_id]['spacing']
        image_pos = "centered"
        if spacing['image_x'] != 0 or spacing['image_y'] != 0:
            image_pos = ""
            if spacing['image_x'] < 0:
                image_pos = f"{abs(spacing['image_x'])}px left"
            elif spacing['image_x'] > 0:
                image_pos = f"{spacing['image_x']}px right"
                
            if spacing['image_y'] != 0:
                if image_pos:
                    image_pos += " and "
                if spacing['image_y'] < 0:
                    image_pos += f"{abs(spacing['image_y'])}px up"
                else:
                    image_pos += f"{spacing['image_y']}px down"
        
        message = f"Great! Using your last preset. Please send me the main image. The reference image will be {image_pos} from center."
    
    await update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardRemove()
    )
    return FIRST_IMAGE

async def first_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save first image and ask for second."""
    user = update.message.from_user
    
    # We'll just store the file_id instead of downloading
    if user.id not in user_data:
        user_data[user.id] = {}
    
    # Set default spacing if not already set
    if 'spacing' not in user_data[user.id]:
        user_data[user.id]['spacing'] = DEFAULT_SPACING.copy()
    
    # Store user info for later
    user_data[user.id]['user_info'] = {
        'id': user.id,
        'first_name': user.first_name,
        'username': user.username if user.username else "Anonymous"
    }
    
    # Check if the message has a photo or document
    if update.message.photo:
        # Get the largest photo
        photo = update.message.photo[-1]
        user_data[user.id]['first_photo'] = photo
        user_data[user.id]['first_is_document'] = False
        logger.info(f"Received main image (photo) from user {user.id}")
    elif update.message.document and update.message.document.mime_type.startswith('image/'):
        # Handle document
        document = update.message.document
        user_data[user.id]['first_photo'] = document
        user_data[user.id]['first_is_document'] = True
        mime_type = update.message.document.mime_type
        user_data[user.id]['first_mime_type'] = mime_type
        logger.info(f"Received main image (document) with MIME type: {mime_type} from user {user.id}")
    else:
        keyboard = [
            [KeyboardButton(CREATE_IMAGE_TEXT)],
            [KeyboardButton(SETTINGS_TEXT)]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Please send an image or photo.",
            reply_markup=reply_markup
        )
        return FIRST_IMAGE
    
    # Add buttons for cancellation
    keyboard = [
        [KeyboardButton(CANCEL_TEXT)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    spacing = user_data[user.id]['spacing']
    
    # Create position description with directional language
    image_pos = "centered"
    if spacing['image_x'] != 0 or spacing['image_y'] != 0:
        image_pos = ""
        if spacing['image_x'] < 0:
            image_pos = f"{abs(spacing['image_x'])}px left"
        elif spacing['image_x'] > 0:
            image_pos = f"{spacing['image_x']}px right"
            
        if spacing['image_y'] != 0:
            if image_pos:
                image_pos += " and "
            if spacing['image_y'] < 0:
                image_pos += f"{abs(spacing['image_y'])}px up"
            else:
                image_pos += f"{spacing['image_y']}px down"
    
    await update.message.reply_text(
        f"Great! Now send me the reference image to place. It will be {image_pos} from center.",
        reply_markup=reply_markup
    )
    return SECOND_IMAGE

async def second_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save second image and ask for name."""
    user = update.message.from_user
    
    # Check if user wants to cancel
    if update.message.text == CANCEL_TEXT:
        return await cancel(update, context)
    
    # Check if the message has a photo or document
    if update.message.photo:
        # Get the largest photo
        photo = update.message.photo[-1]
        user_data[user.id]['second_photo'] = photo
        user_data[user.id]['second_is_document'] = False
        logger.info(f"Received reference image (photo) from user {user.id}")
    elif update.message.document and update.message.document.mime_type.startswith('image/'):
        # Handle document
        document = update.message.document
        user_data[user.id]['second_photo'] = document
        user_data[user.id]['second_is_document'] = True
        mime_type = update.message.document.mime_type
        user_data[user.id]['second_mime_type'] = mime_type
        logger.info(f"Received reference image (document) with MIME type: {mime_type} from user {user.id}")
    else:
        keyboard = [
            [KeyboardButton(CANCEL_TEXT)]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Please send an image or photo.",
            reply_markup=reply_markup
        )
        return SECOND_IMAGE
    
    # Add button for cancellation
    keyboard = [
        [KeyboardButton(CANCEL_TEXT)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Perfect! Now send me the text to add to the image:",
        reply_markup=reply_markup
    )
    return NAME

async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process images with the provided name."""
    user = update.message.from_user
    
    # Check if user wants to cancel
    if update.message.text == CANCEL_TEXT:
        return await cancel(update, context)
        
    name = update.message.text
    
    logger.info(f"Received name from user {user.id}: {name}")
    await update.message.reply_text("Processing your images... Please wait.")
    
    try:
        # Download both images
        first_photo = user_data[user.id]['first_photo']
        second_photo = user_data[user.id]['second_photo']
        
        # Get file objects
        first_file = await first_photo.get_file()
        second_file = await second_photo.get_file()
        
        # Download to memory
        first_image_data = BytesIO()
        second_image_data = BytesIO()
        
        await first_file.download_to_memory(first_image_data)
        await second_file.download_to_memory(second_image_data)
        
        # Reset pointers
        first_image_data.seek(0)
        second_image_data.seek(0)
        
        # Check if we need to preserve transparency
        has_transparency = False
        if user_data[user.id].get('first_is_document') and user_data[user.id].get('first_mime_type') == 'image/png':
            has_transparency = True
        if user_data[user.id].get('second_is_document') and user_data[user.id].get('second_mime_type') == 'image/png':
            has_transparency = True
            
        # Open with PIL - preserve transparency if needed
        if has_transparency:
            main_img = Image.open(first_image_data).convert("RGBA")
            ref_img = Image.open(second_image_data).convert("RGBA")
            logger.info("Using RGBA mode to preserve transparency")
        else:
            main_img = Image.open(first_image_data).convert("RGB")
            ref_img = Image.open(second_image_data).convert("RGB")
            logger.info("Using RGB mode")
        
        # Get dimensions
        main_width, main_height = main_img.size
        
        # Resize reference image to REF_IMAGE_SIZE x REF_IMAGE_SIZE
        ref_img = ref_img.resize((REF_IMAGE_SIZE, REF_IMAGE_SIZE))
        
        # Get spacing settings from user data
        spacing = user_data[user.id]['spacing']
        
        # Calculate position based on offsets from center
        ref_center_x = main_width // 2
        ref_center_y = main_height // 2
        
        # Apply the X and Y offsets for the reference image 
        x_position = ref_center_x - (REF_IMAGE_SIZE // 2) + spacing['image_x']
        y_position = ref_center_y - (REF_IMAGE_SIZE // 2) + spacing['image_y']
        
        # Make sure image stays within boundaries
        x_position = max(0, min(x_position, main_width - REF_IMAGE_SIZE))
        y_position = max(0, min(y_position, main_height - REF_IMAGE_SIZE))
        
        # Paste reference image
        if has_transparency:
            # Create a new transparent image
            result = Image.new('RGBA', main_img.size, (0, 0, 0, 0))
            # Paste main image first
            result.paste(main_img, (0, 0), main_img if main_img.mode == 'RGBA' else None)
            # Paste reference image with alpha channel at the calculated position
            result.paste(ref_img, (x_position, y_position), ref_img)
            main_img = result
        else:
            main_img.paste(ref_img, (x_position, y_position))
        
        # Add text
        draw = ImageDraw.Draw(main_img)
        
        # Try to download and use Boldonse font first
        try:
            font = None
            
            # Try to download the font if it doesn't exist
            if not os.path.exists(FONT_FILE_PATH):
                download_success = download_font()
                if not download_success:
                    raise Exception("Failed to download Boldonse font")
            
            # Use the downloaded Boldonse font
            if os.path.exists(FONT_FILE_PATH):
                font = ImageFont.truetype(FONT_FILE_PATH, FONT_SIZE)
                logger.info(f"Using Boldonse font from: {FONT_FILE_PATH}")
            
            if font is None:
                # Fallback font paths
                font_paths = [
                    "/System/Library/Fonts/Courier.ttc",  # macOS
                    "/System/Library/Fonts/Monaco.ttf",   # macOS
                    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",  # Linux
                    "C:\\Windows\\Fonts\\consola.ttf",    # Windows
                    "C:\\Windows\\Fonts\\cour.ttf",       # Windows
                    "/System/Library/Fonts/Menlo.ttc",    # macOS
                ]
                
                for path in font_paths:
                    try:
                        if os.path.exists(path):
                            font = ImageFont.truetype(path, FONT_SIZE)
                            logger.info(f"Using fallback font from: {path}")
                            break
                    except Exception as font_e:
                        logger.warning(f"Could not load font from {path}: {font_e}")
                        
            if font is None:
                logger.warning("No fonts found, using default")
                font = ImageFont.load_default()
                
        except Exception as e:
            logger.warning(f"Error loading fonts: {e}")
            font = ImageFont.load_default()
        
        # Get text dimensions
        text_width = font.getbbox(name)[2] - font.getbbox(name)[0]
        text_height = font.getbbox(name)[3] - font.getbbox(name)[1]
        
        # Position text with center as reference point plus offsets
        text_x = (main_width - text_width) // 2 + spacing['text_x']
        text_y = main_height - text_height - 30 + spacing['text_y'] # Default position near bottom
        
        # Make sure text stays within boundaries
        text_x = max(10, min(text_x, main_width - text_width - 10))
        text_y = max(10, min(text_y, main_height - text_height - 10))
        
        # Add white text with black outline for better visibility
        draw.text((text_x-1, text_y-1), name, fill="black", font=font)
        draw.text((text_x+1, text_y-1), name, fill="black", font=font)
        draw.text((text_x-1, text_y+1), name, fill="black", font=font)
        draw.text((text_x+1, text_y+1), name, fill="black", font=font)
        draw.text((text_x, text_y), name, fill="white", font=font)
        
        # Save format depends on transparency
        output = BytesIO()
        if has_transparency:
            # Save as PNG to preserve transparency
            main_img.save(output, format="PNG")
            output_format = "PNG"
            output.name = "merged_image.png"
        else:
            # Save as JPEG (more reliable with Telegram for non-transparent images)
            main_img.save(output, format="JPEG", quality=95)
            output_format = "JPEG"
            output.name = "merged_image.jpg"
            
        logger.info(f"Saved output as {output_format}")
        output.seek(0)
        
        # Save a copy for the group
        group_output = BytesIO()
        if has_transparency:
            main_img.save(group_output, format="PNG")
            group_output.name = "merged_image.png"
        else:
            main_img.save(group_output, format="JPEG", quality=95)
            group_output.name = "merged_image.jpg"
        group_output.seek(0)
        
        # Send the image to the user
        sent_message = await update.message.reply_document(document=output)
        
        # Get user info
        user_info = user_data[user.id]['user_info']
        
        # Send to the group
        try:
            # Create caption with user info
            caption = f"Created by {user_info['first_name']} (@{user_info['username']})\nText: {name}"
            
            # Send as a new message to the group, not as a forward
            await context.bot.send_document(
                chat_id=f"@{GROUP_CHAT_ID}",
                document=group_output,
                caption=caption
            )
            logger.info(f"Successfully sent merged image to group @{GROUP_CHAT_ID}")
        except Exception as e:
            logger.error(f"Error sending to group: {e}")
            await update.message.reply_text("Note: Could not share to the group channel. Please check bot permissions.")
        
        # Clean up user data but preserve settings
        settings_data = {}
        if 'spacing' in user_data[user.id]:
            settings_data['spacing'] = user_data[user.id]['spacing']
            
        user_data[user.id] = settings_data
        
        # Add buttons to create a new image or adjust settings
        keyboard = [
            [KeyboardButton(CREATE_IMAGE_TEXT)],
            [KeyboardButton(SETTINGS_TEXT)]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Confirm success
        await update.message.reply_text(
            "Here's your merged image! It has also been shared to the group.",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error processing images: {e}", exc_info=True)
        await update.message.reply_text(f"Error: {str(e)}. Please try again.")
        
        # Add button to restart
        keyboard = [
            [KeyboardButton(CREATE_IMAGE_TEXT)],
            [KeyboardButton(SETTINGS_TEXT)]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Click below to try again:", 
            reply_markup=reply_markup
        )
        
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel conversation."""
    user = update.message.from_user
    
    # Preserve settings but clear other data
    settings_data = {}
    if user.id in user_data:
        if 'spacing' in user_data[user.id]:
            settings_data['spacing'] = user_data[user.id]['spacing']
        user_data[user.id] = settings_data
    
    keyboard = [
        [KeyboardButton(CREATE_IMAGE_TEXT)],
        [KeyboardButton(SETTINGS_TEXT)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Operation cancelled.", 
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END

async def delete_preset_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show menu to select which preset to delete"""
    # Check if user wants to go back
    if update.message.text == BACK_TEXT:
        return await settings(update, context)
        
    # Load existing presets
    presets = load_presets()
    
    if not presets:
        await update.message.reply_text(
            "No presets found to delete.",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(BACK_TEXT)]
            ], resize_keyboard=True)
        )
        return PRESETS
    
    keyboard = []
    
    # Add buttons for each preset
    for preset_name, preset_data in presets.items():
        if "spacing" in preset_data:
            spacing = preset_data["spacing"]
            
            # Create directional description for the preset
            image_pos = "Center"
            if spacing.get('image_x', 0) < 0:
                image_pos = f"{abs(spacing.get('image_x', 0))}px Left"
            elif spacing.get('image_x', 0) > 0:
                image_pos = f"{spacing.get('image_x', 0)}px Right"
                
            if spacing.get('image_y', 0) != 0:
                if spacing.get('image_y', 0) < 0:
                    image_pos += f", {abs(spacing.get('image_y', 0))}px Up"
                else:
                    image_pos += f", {spacing.get('image_y', 0)}px Down"
                    
            keyboard.append([
                KeyboardButton(f"Delete: {preset_name} ({image_pos})")
            ])
    
    keyboard.append([KeyboardButton(BACK_TEXT)])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Select which preset you want to delete:",
        reply_markup=reply_markup
    )
    
    return DELETE_PRESET

async def delete_preset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle deletion of a preset"""
    # Check if user wants to go back
    if update.message.text == BACK_TEXT:
        return await presets_menu(update, context)
    
    # Extract preset name from text
    text = update.message.text
    if text.startswith("Delete:"):
        # Extract just the name part before any description in parentheses
        preset_name = text.replace("Delete:", "").split(" (")[0].strip()
        
        # Load presets
        presets = load_presets()
        
        if preset_name in presets:
            # Delete the preset
            del presets[preset_name]
            
            # Save updated presets
            if save_presets(presets):
                await update.message.reply_text(
                    f"Preset '{preset_name}' deleted successfully!",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton(BACK_TEXT)]
                    ], resize_keyboard=True)
                )
            else:
                await update.message.reply_text(
                    "Error deleting preset. Please try again.",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton(BACK_TEXT)]
                    ], resize_keyboard=True)
                )
        else:
            await update.message.reply_text(
                "Error: Preset not found.",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton(BACK_TEXT)]
                ], resize_keyboard=True)
            )
    else:
        await update.message.reply_text(
            "Please select a preset to delete.",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(BACK_TEXT)]
            ], resize_keyboard=True)
        )
    
    return DELETE_PRESET

async def load_preset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Load a selected preset"""
    user_id = update.message.from_user.id
    
    # Get the preset name from context or extract from message text
    if hasattr(context, 'user_data') and "selected_preset" in context.user_data:
        preset_name = context.user_data["selected_preset"]
        del context.user_data["selected_preset"]
    else:
        text = update.message.text
        if text.startswith("Preset:"):
            # Extract just the name part before any description in parentheses
            preset_name = text.replace("Preset:", "").split(" (")[0].strip()
        else:
            await update.message.reply_text(
                "Error: Could not identify preset.",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton(BACK_TEXT)]
                ], resize_keyboard=True)
            )
            return SETTINGS
    
    # Load presets
    presets = load_presets()
    
    if preset_name in presets:
        # Apply the preset
        preset_data = presets[preset_name]
        
        if user_id not in user_data:
            user_data[user_id] = {}
        
        # Ensure spacing dictionary has all required keys
        if 'spacing' in preset_data:
            spacing = preset_data["spacing"].copy()
            
            # Add any missing keys with defaults
            if "image_x" not in spacing:
                spacing["image_x"] = 0
            if "image_y" not in spacing:
                spacing["image_y"] = 0
            if "text_x" not in spacing:
                spacing["text_x"] = 0
            if "text_y" not in spacing:
                spacing["text_y"] = 0
                
            user_data[user_id]['spacing'] = spacing
            
            # Store the last used preset name
            user_data[user_id]['last_preset'] = preset_name
        else:
            # If no spacing in preset, use defaults
            user_data[user_id]['spacing'] = DEFAULT_SPACING.copy()
        
        await update.message.reply_text(
            f"Preset '{preset_name}' loaded successfully!",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(BACK_TEXT)]
            ], resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            "Error: Preset not found.",
            reply_markup=ReplyKeyboardMarkup([
                [KeyboardButton(BACK_TEXT)]
            ], resize_keyboard=True)
        )
    
    return SETTINGS

def main() -> None:
    """Start the bot."""
    # Get token
    token = os.getenv("TELEGRAM_TOKEN", "8125048019:AAHSoPTvoybOkwtCLvWO_4I_PXNthWpqEtM")
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("settings", settings),
            MessageHandler(filters.Regex(f"^{CREATE_IMAGE_TEXT}$"), start_new_image),
            MessageHandler(filters.Regex(f"^{SETTINGS_TEXT}$"), settings)
        ],
        states={
            FIRST_IMAGE: [
                MessageHandler(filters.PHOTO, first_image),
                MessageHandler(filters.Document.IMAGE, first_image),
                MessageHandler(filters.Regex(f"^{CANCEL_TEXT}$"), cancel)
            ],
            SECOND_IMAGE: [
                MessageHandler(filters.PHOTO, second_image),
                MessageHandler(filters.Document.IMAGE, second_image),
                MessageHandler(filters.Regex(f"^{CANCEL_TEXT}$"), cancel)
            ],
            NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_name)
            ],
            SETTINGS: [
                MessageHandler(filters.Regex(f"^{CUSTOM_SPACING_TEXT}.*$"), custom_spacing_menu),
                MessageHandler(filters.Regex(f"^{PRESETS_TEXT}$"), presets_menu),
                MessageHandler(filters.Regex(f"^{SAVE_PRESET_TEXT}$"), save_preset_prompt),
                MessageHandler(filters.Regex(f"^{DONE_TEXT}$"), done_settings),
                MessageHandler(filters.Regex(f"^{CREATE_IMAGE_TEXT}$"), start_new_image),
                MessageHandler(filters.Regex(f"^Preset:.*$"), load_preset)
            ],
            CUSTOM_SPACING: [
                MessageHandler(filters.Regex(f"^{IMAGE_X_TEXT}.*|{IMAGE_Y_TEXT}.*|{TEXT_X_TEXT}.*|{TEXT_Y_TEXT}.*|{BACK_TEXT}$"), handle_direction_selection)
            ],
            SPACING_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_spacing_input)
            ],
            PRESET_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_preset)
            ],
            PRESETS: [
                MessageHandler(filters.Regex(f"^Preset:.*$"), load_preset),
                MessageHandler(filters.Regex(f"^{SAVE_PRESET_TEXT}$"), save_preset_prompt),
                MessageHandler(filters.Regex(f"^{EDIT_PRESET_TEXT}$"), edit_preset_select),
                MessageHandler(filters.Regex(f"^{DELETE_PRESET_TEXT}$"), delete_preset_select),
                MessageHandler(filters.Regex(f"^{BACK_TEXT}$"), settings)
            ],
            DELETE_PRESET: [
                MessageHandler(filters.Regex(f"^Delete:.*$"), delete_preset),
                MessageHandler(filters.Regex(f"^{BACK_TEXT}$"), presets_menu)
            ],
            EDIT_PRESET: [
                MessageHandler(filters.Regex(f"^Edit:.*$"), edit_preset),
                MessageHandler(filters.Regex(f"^{BACK_TEXT}$"), presets_menu)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.Regex(f"^{CANCEL_TEXT}$"), cancel)
        ],
    )
    
    application.add_handler(conv_handler)
    
    # Add handler for any text commands from keyboards
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        command_handler
    ))
    
    # Run the bot
    print("Starting merger bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 