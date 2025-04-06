import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text("Hi! Send me an image and I'll send it back to you.")

async def echo_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user image."""
    try:
        # Get the largest photo from the message
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        logger.info(f"Received image with file_id: {file_id}")
        await update.message.reply_text(f"Received your image! Sending it back...")
        
        # Simply send back the same file_id - this is the simplest way
        await update.message.reply_photo(photo=file_id)
        
        logger.info("Sent image back successfully")
        await update.message.reply_text("Image sent back successfully!")
    except Exception as e:
        logger.error(f"Error processing photo: {e}", exc_info=True)
        await update.message.reply_text(f"Error: {str(e)}. Please try again.")

def main() -> None:
    """Start the bot."""
    # Get token
    token = os.getenv("TELEGRAM_TOKEN", "8125048019:AAHSoPTvoybOkwtCLvWO_4I_PXNthWpqEtM")
    
    # Create application
    application = Application.builder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.PHOTO, echo_image))

    # Run the bot
    print("Starting basic bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 