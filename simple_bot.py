import os
import logging
import sys
from io import BytesIO
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from PIL import Image, ImageDraw, ImageFont

# Enable detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Conversation states
FIRST_IMAGE, SECOND_IMAGE, NAME = range(3)

# User session storage
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Hi! Send me the main image first.')
    return FIRST_IMAGE

async def first_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    photo_file = await update.message.photo[-1].get_file()
    
    bio = BytesIO()
    await photo_file.download_to_memory(bio)
    bio.seek(0)
    
    if not user.id in user_data:
        user_data[user.id] = {}
    user_data[user.id]['first_image'] = bio
    
    logger.info(f"Received main image from user {user.id}")
    
    await update.message.reply_text('Now send me the reference image for the center.')
    return SECOND_IMAGE

async def second_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    photo_file = await update.message.photo[-1].get_file()
    
    bio = BytesIO()
    await photo_file.download_to_memory(bio)
    bio.seek(0)
    
    user_data[user.id]['second_image'] = bio
    
    logger.info(f"Received reference image from user {user.id}")
    
    await update.message.reply_text('Now send me the name to add at the bottom.')
    return NAME

async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    name = update.message.text
    user_data[user.id]['name'] = name
    
    logger.info(f"Processing images for user {user.id} with name: {name}")
    await update.message.reply_text('Processing your images... Please wait.')
    
    try:
        # Reset file pointers
        user_data[user.id]['first_image'].seek(0)
        user_data[user.id]['second_image'].seek(0)
        
        # Open images
        main_img = Image.open(user_data[user.id]['first_image']).convert('RGBA')
        ref_img = Image.open(user_data[user.id]['second_image']).convert('RGBA')
        
        # Log image details
        logger.info(f"Main image: {main_img.size} mode={main_img.mode}")
        logger.info(f"Ref image: {ref_img.size} mode={ref_img.mode}")
        
        # Resize reference image to 60x60
        ref_img = ref_img.resize((60, 60))
        
        # Calculate center position
        main_width, main_height = main_img.size
        x_position = (main_width - 60) // 2
        y_position = (main_height - 60) // 2
        
        # Simplified image merging - create a new image and paste both
        result = Image.new('RGBA', main_img.size)
        result.paste(main_img, (0, 0))
        result.paste(ref_img, (x_position, y_position), ref_img)
        
        # Add text at bottom
        draw = ImageDraw.Draw(result)
        font = ImageFont.load_default()
        
        # Calculate text width for centering
        text_width = 0
        if hasattr(draw, "textlength"):
            text_width = draw.textlength(name, font=font)
        elif hasattr(font, "getlength"):
            text_width = font.getlength(name)
        else:
            text_width = font.getsize(name)[0]
        
        text_x = (main_width - text_width) // 2
        text_y = main_height - 30
        
        # Add white text with black outline
        draw.text((text_x-1, text_y-1), name, fill="black", font=font)
        draw.text((text_x+1, text_y-1), name, fill="black", font=font)
        draw.text((text_x-1, text_y+1), name, fill="black", font=font)
        draw.text((text_x+1, text_y+1), name, fill="black", font=font)
        draw.text((text_x, text_y), name, fill="white", font=font)
        
        # Save to disk first
        output_path = f"output_{user.id}.png"
        result.save(output_path)
        logger.info(f"Saved result to {output_path}")
        
        # Check file size
        file_size = os.path.getsize(output_path)
        logger.info(f"Output file size: {file_size} bytes")
        
        if file_size > 10000000:  # 10MB Telegram limit
            logger.warning("File too large, reducing size")
            # Resize to reduce file size if needed
            width, height = result.size
            result = result.resize((width // 2, height // 2))
            result.save(output_path)
            
        # Send from disk (more reliable)
        with open(output_path, 'rb') as photo:
            logger.info("Sending photo from disk...")
            await update.message.reply_photo(photo=photo)
            logger.info("Photo sent successfully")
        
        # Cleanup
        if user.id in user_data:
            del user_data[user.id]
            
        await update.message.reply_text('Here is your merged image! Type /start to create another one.')
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error processing images: {str(e)}", exc_info=True)
        await update.message.reply_text(f'Error: {str(e)}. Try again with /start')
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    if user.id in user_data:
        del user_data[user.id]
    await update.message.reply_text('Operation cancelled. Send /start to try again.')
    return ConversationHandler.END

if __name__ == '__main__':
    # Get token from environment or use default
    token = os.getenv('TELEGRAM_TOKEN', '8125048019:AAHSoPTvoybOkwtCLvWO_4I_PXNthWpqEtM')
    
    print(f"Starting bot with token: {token[:8]}...")
    
    try:
        # Set up application
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
        
        # Start the bot
        print("Bot is running. Press Ctrl+C to stop.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        print(f"Error starting bot: {e}")
        sys.exit(1) 