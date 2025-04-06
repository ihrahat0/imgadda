import os
import logging
import asyncio
import nest_asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from dotenv import load_dotenv

# Apply nest_asyncio to allow nested event loops (fixes "event loop already running" errors)
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants for conversation states
FIRST_IMAGE, SECOND_IMAGE, NAME = range(3)

# User session storage
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask for the first image."""
    await update.message.reply_text(
        'Hi! I will help you merge two images. Please send me the main image first.'
    )
    return FIRST_IMAGE

async def first_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the first image and ask for the second one."""
    user = update.message.from_user
    photo_file = await update.message.photo[-1].get_file()
    
    # Store the file in memory
    bio = BytesIO()
    await photo_file.download_to_memory(bio)
    bio.seek(0)
    
    # Save data for this user
    if not user.id in user_data:
        user_data[user.id] = {}
    user_data[user.id]['first_image'] = bio
    
    await update.message.reply_text(
        'Great! Now please send me the reference image that will be placed in the center.'
    )
    return SECOND_IMAGE

async def second_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store the second image and ask for a name."""
    user = update.message.from_user
    photo_file = await update.message.photo[-1].get_file()
    
    # Store the file in memory
    bio = BytesIO()
    await photo_file.download_to_memory(bio)
    bio.seek(0)
    
    # Save the second image
    user_data[user.id]['second_image'] = bio
    
    await update.message.reply_text(
        'Perfect! Now please send me the name you want to add to the bottom of the image.'
    )
    return NAME

async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the name and create the final image."""
    user = update.message.from_user
    user_data[user.id]['name'] = update.message.text
    
    await update.message.reply_text('Processing your images... Please wait.')
    
    # Process images
    try:
        # Open both images
        main_img = Image.open(user_data[user.id]['first_image'])
        ref_img = Image.open(user_data[user.id]['second_image'])
        
        # Resize reference image to 60x60 pixels
        ref_img = ref_img.resize((60, 60))
        
        # Calculate the center position
        main_width, main_height = main_img.size
        ref_width, ref_height = ref_img.size
        
        x_position = (main_width - ref_width) // 2
        y_position = (main_height - ref_height) // 2
        
        # Ensure the main image has an alpha channel
        if main_img.mode != 'RGBA':
            main_img = main_img.convert('RGBA')
        
        # Paste the reference image in the center
        main_img.paste(ref_img, (x_position, y_position), mask=ref_img.convert('RGBA') if ref_img.mode != 'RGBA' else ref_img)
        
        # Add the name to the bottom center
        draw = ImageDraw.Draw(main_img)
        
        # Try to load a font, use default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except IOError:
            font = ImageFont.load_default()
        
        name = user_data[user.id]['name']
        text_width = 0
        # Check Pillow version for text width calculation
        if hasattr(draw, "textlength"):
            text_width = draw.textlength(name, font=font)
        elif hasattr(font, "getlength"):
            text_width = font.getlength(name)
        else:
            # Fallback for older Pillow versions
            text_width = font.getsize(name)[0]
        
        name_position = ((main_width - text_width) // 2, main_height - 30)
        
        # Add white text with black outline for better visibility
        draw.text((name_position[0]-1, name_position[1]-1), name, font=font, fill="black")
        draw.text((name_position[0]+1, name_position[1]-1), name, font=font, fill="black")
        draw.text((name_position[0]-1, name_position[1]+1), name, font=font, fill="black")
        draw.text((name_position[0]+1, name_position[1]+1), name, font=font, fill="black")
        draw.text(name_position, name, font=font, fill="white")
        
        # Save the result to a bytes buffer
        output = BytesIO()
        main_img.save(output, format='PNG')
        output.seek(0)
        
        # Send the result back
        await update.message.reply_photo(output)
        
        # Clean up user data
        del user_data[user.id]
        
        await update.message.reply_text(
            'Here is your merged image! Send /start to create another one.'
        )
    except Exception as e:
        logger.error(f"Error processing images: {e}")
        await update.message.reply_text(
            f'Sorry, something went wrong: {str(e)}. Please try again with /start.'
        )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel and end the conversation."""
    user = update.message.from_user
    if user.id in user_data:
        del user_data[user.id]
    
    await update.message.reply_text('Operation cancelled. Send /start to try again.')
    return ConversationHandler.END

async def main() -> None:
    """Start the bot."""
    # Use the bot token from environment variable or directly
    token = os.getenv('TELEGRAM_TOKEN', '8125048019:AAHSoPTvoybOkwtCLvWO_4I_PXNthWpqEtM')
    
    # Create the Application
    application = Application.builder().token(token).build()
    
    # Set up conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            FIRST_IMAGE: [MessageHandler(filters.PHOTO & ~filters.COMMAND, first_image)],
            SECOND_IMAGE: [MessageHandler(filters.PHOTO & ~filters.COMMAND, second_image)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_name)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    
    # Start the Bot
    await application.run_polling()

if __name__ == '__main__':
    try:
        # Try to run with asyncio.run (preferred way)
        asyncio.run(main())
    except RuntimeError as e:
        # If there's already a running event loop, use get_event_loop
        if "event loop" in str(e).lower():
            logger.info("An event loop is already running, using existing loop")
            loop = asyncio.get_event_loop()
            loop.create_task(main())
            # Keep the main thread alive if not in interactive mode
            if not loop.is_running():
                loop.run_forever()
        else:
            # If it's a different error, raise it
            raise 