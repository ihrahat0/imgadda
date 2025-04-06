import os
import logging
import sys
import traceback
from io import BytesIO
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
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
    
    logger.info(f"Received first image from user {user.id}")
    
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
    
    logger.info(f"Received second image from user {user.id}")
    
    await update.message.reply_text(
        'Perfect! Now please send me the name you want to add to the bottom of the image.'
    )
    return NAME

async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the name and create the final image."""
    user = update.message.from_user
    user_data[user.id]['name'] = update.message.text
    
    logger.info(f"Received name from user {user.id}: {update.message.text}")
    
    await update.message.reply_text('Processing your images... Please wait.')
    
    # Process images
    try:
        # Save original files to disk for debugging
        try:
            user_data[user.id]['first_image'].seek(0)
            with open(f'debug_main_image_{user.id}.png', 'wb') as f:
                f.write(user_data[user.id]['first_image'].getvalue())
            
            user_data[user.id]['second_image'].seek(0)
            with open(f'debug_ref_image_{user.id}.png', 'wb') as f:
                f.write(user_data[user.id]['second_image'].getvalue())
                
            logger.info(f"Saved debug images to disk for user {user.id}")
        except Exception as e:
            logger.error(f"Error saving debug files: {e}")
        
        # Reset file pointers
        user_data[user.id]['first_image'].seek(0)
        user_data[user.id]['second_image'].seek(0)
        
        # Open both images
        main_img = Image.open(user_data[user.id]['first_image'])
        ref_img = Image.open(user_data[user.id]['second_image'])
        
        # Print image info for debugging
        logger.info(f"Main image mode: {main_img.mode}, size: {main_img.size}")
        logger.info(f"Reference image mode: {ref_img.mode}, size: {ref_img.size}")
        
        # Convert both images to RGBA
        if main_img.mode != 'RGBA':
            main_img = main_img.convert('RGBA')
            logger.info("Converted main image to RGBA")
        if ref_img.mode != 'RGBA':
            ref_img = ref_img.convert('RGBA')
            logger.info("Converted reference image to RGBA")
        
        # Save converted images for debugging
        main_img.save(f'debug_main_converted_{user.id}.png')
        ref_img.save(f'debug_ref_converted_{user.id}.png')
        
        # Resize reference image to 60x60 pixels
        ref_img = ref_img.resize((60, 60))
        logger.info(f"Resized reference image to 60x60 pixels")
        
        # Calculate the center position
        main_width, main_height = main_img.size
        ref_width, ref_height = ref_img.size
        
        x_position = (main_width - ref_width) // 2
        y_position = (main_height - ref_height) // 2
        
        logger.info(f"Calculated center position: ({x_position}, {y_position})")
        
        # Alternative approach for pasting images
        # Create a new empty image with the same size as main_img
        new_img = Image.new('RGBA', main_img.size, (0, 0, 0, 0))
        # Paste the main image onto the new image
        new_img.paste(main_img, (0, 0))
        # Paste the reference image onto the new image
        new_img.paste(ref_img, (x_position, y_position), ref_img)
        
        # Replace main_img with new_img
        main_img = new_img
        
        logger.info("Pasted reference image onto main image")
        
        # Save intermediate result for debugging
        main_img.save(f'debug_merged_{user.id}.png')
        
        # Add the name to the bottom center
        draw = ImageDraw.Draw(main_img)
        
        # Try to load a font, use default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 20)
            logger.info("Loaded Arial font")
        except IOError:
            try:
                # Try a different system font
                font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 20)
                logger.info("Loaded system Arial font")
            except IOError:
                font = ImageFont.load_default()
                logger.info("Using default font")
        
        name = user_data[user.id]['name']
        text_width = 0
        
        # Check Pillow version for text width calculation
        if hasattr(draw, "textlength"):
            text_width = draw.textlength(name, font=font)
            logger.info("Used draw.textlength for text width")
        elif hasattr(font, "getlength"):
            text_width = font.getlength(name)
            logger.info("Used font.getlength for text width")
        else:
            # Fallback for older Pillow versions
            text_width = font.getsize(name)[0]
            logger.info("Used font.getsize for text width")
        
        name_position = ((main_width - text_width) // 2, main_height - 30)
        logger.info(f"Text position: {name_position}")
        
        # Add white text with black outline for better visibility
        draw.text((name_position[0]-1, name_position[1]-1), name, font=font, fill="black")
        draw.text((name_position[0]+1, name_position[1]-1), name, font=font, fill="black")
        draw.text((name_position[0]-1, name_position[1]+1), name, font=font, fill="black")
        draw.text((name_position[0]+1, name_position[1]+1), name, font=font, fill="black")
        draw.text(name_position, name, font=font, fill="white")
        
        logger.info("Added text to image")
        
        # Save final image to disk for debugging
        main_img.save(f'final_image_{user.id}.png')
        logger.info(f"Saved final image to disk: final_image_{user.id}.png")
        
        # Save the result to a bytes buffer
        output = BytesIO()
        main_img.save(output, format='PNG')
        output.seek(0)
        
        logger.info("Saved image to BytesIO buffer")
        
        # Try to send both the BytesIO buffer and the file from disk as fallback
        try:
            # First try with BytesIO
            await update.message.reply_photo(output)
            logger.info("Sent image using BytesIO buffer")
        except Exception as e:
            logger.error(f"Error sending image via BytesIO: {e}")
            try:
                # Try with file on disk as fallback
                with open(f'final_image_{user.id}.png', 'rb') as photo:
                    await update.message.reply_photo(photo)
                logger.info("Sent image using file on disk")
            except Exception as e2:
                logger.error(f"Error sending image from disk: {e2}")
                # Send the error message
                await update.message.reply_text(
                    f'Error sending the image. Please try again with /start.'
                )
        
        # Clean up user data
        del user_data[user.id]
        
        await update.message.reply_text(
            'Here is your merged image! Send /start to create another one.'
        )
    except Exception as e:
        logger.error(f"Error processing images: {str(e)}")
        logger.error(traceback.format_exc())
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

if __name__ == '__main__':
    # Get token from environment or use default
    token = os.getenv('TELEGRAM_TOKEN', '8125048019:AAHSoPTvoybOkwtCLvWO_4I_PXNthWpqEtM')
    
    # Display startup message
    print("Starting Telegram Bot...")
    print(f"Bot token: {token[:8]}...{token[-8:]}")
    
    try:
        # Build application
        application = Application.builder().token(token).build()
        
        # Add conversation handler
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
        
        # Run the bot with explicit event loop management
        print("Bot is running. Press Ctrl+C to stop.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Error starting the bot: {e}")
        print(f"Failed to start the bot: {e}")
        sys.exit(1) 