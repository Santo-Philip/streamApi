import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
import uuid

from database.video import video_exists

que = asyncio.Queue()
pending_tasks = []


@Client.on_message(filters.command('upload'))
async def upload(bot: Client, msg: Message):
    replied_message = msg.reply_to_message
    file_id = None
    file_name = None

    if replied_message.video:
        file_id = replied_message.video.file_unique_id
        file_name = replied_message.video.file_name
    elif replied_message.document:
        file_id = replied_message.document.file_unique_id
        file_name = replied_message.document.file_name

    exists = video_exists(file_id)

    if exists is not None:
        await msg.reply_text('The file is already available in the database')
        return

    if not replied_message or not (replied_message.video or (
            replied_message.document and replied_message.document.mime_type.startswith("video/"))):
        return await msg.reply_text("❌ The replied message does not contain a video.")

    queue_position = que.qsize() + 1
    progress_message = await msg.reply_text(f"📥 Queued at position #{queue_position}\nWaiting...")

    # Progress variables
    progress_data = {"current": 0, "total": 1}  # Default values
    stop_progress = False

    async def progress_callback(current, total):
        progress_data["current"] = current
        progress_data["total"] = total

    async def update_progress():
        while not stop_progress:
            if progress_data["total"] > 1:  # Avoid division by zero
                percent = (progress_data["current"] / progress_data["total"]) * 100
                bar_length = 20
                filled_length = int(bar_length * percent / 100)
                bar = "█" * filled_length + " " * (bar_length - filled_length)

                try:
                    await progress_message.edit_text(
                        f"📥 Downloading (Queue #{queue_position})...\n\n[{bar}] {percent:.2f}%"
                    )
                except Exception:
                    pass  # Ignore errors

            await asyncio.sleep(3)  # Update every 3 seconds

    if not file_id or not file_name:
        return await msg.reply_text("❌ Failed to extract video details.")

    # Start progress update loop
    progress_task = asyncio.create_task(update_progress())

    file_path = await replied_message.download(progress=progress_callback)

    stop_progress = True  # Stop updating progress once download completes
    await progress_task  # Wait for the update loop to finish

    video_data = {
        "file_id": file_id,
        "file_name": file_name,
        "file_path": file_path,
        "chat_id": msg.chat.id,
        "user_id": msg.from_user.id,
        "bot": bot,
        "progress": progress_message,
        "msg" : msg
    }

    await que.put(video_data)  # Save in queue
    pending_tasks.append(video_data)

    await progress_message.edit_text(
        f"✅ Download Complete! 🎉\n📌 Your video is in the queue at position #{queue_position}.\n⚙️ Processing will start soon... Please wait! ⏳"
    )
