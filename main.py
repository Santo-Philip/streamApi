import asyncio
import logging
import os

from pyrogram import Client, idle, filters
from plugins.encoder import encode_video
from web.initial import start_web_server
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

api_id = 1474940
api_hash = "779e8d2b32ef76d0b7a11fb5f132a6b6"
bot_token = os.getenv('BOT_TOKEN')

# Initialize Pyrogram client
app = Client(
    "my_bot",
    api_id=api_id,
    api_hash=api_hash,
    bot_token=bot_token,
    plugins=dict(root="plugins"),
    max_concurrent_transmissions=6,
)

async def main():
    encoding_task = None
    web_server_task = None

    try:
        logger.info("Starting the bot...")
        await app.start()
        logger.info("Bot started successfully.")

        logger.info("Starting video encoding task...")

        logger.info("Starting the web server...")
        web_server_task = asyncio.create_task(start_web_server())

        logger.info("AioHttp Started. Entering idle mode...")
        await idle()

    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)

    finally:
        logger.info("Shutting down...")

        # Cancel encoding task if it was started
        if encoding_task is not None:
            encoding_task.cancel()
            try:
                await asyncio.wait_for(encoding_task, timeout=5.0)
                logger.info("Encoding task stopped.")
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.info("Encoding task cancelled or timed out.")

        # Cancel web server task if it was started
        if web_server_task is not None:
            web_server_task.cancel()
            try:
                await asyncio.wait_for(web_server_task, timeout=5.0)
                logger.info("Web server task stopped.")
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.info("Web server task cancelled or timed out.")

        try:
            await app.stop()
            logger.info("Bot stopped successfully.")
        except Exception as e:
            logger.error(f"Error stopping bot: {e}")


if __name__ == "__main__":
    logger.info("Starting the program...")
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(encode_video())
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, stopping gracefully...")
