from pyrogram import Client, filters
from pyrogram.types import Message


@Client.on_message(filters.command('check'))
async def file_check(bot: Client, msg: Message):
    replied_message = msg.reply_to_message
    if not replied_message:
        await msg.reply("Please reply to a video!")
        return

    if replied_message.video:
        print("File Unique ID:", replied_message.video.file_unique_id)
        print("File ID:", replied_message.video.file_id)
        await msg.reply(f"📂 Video File Unique ID: `{replied_message.video.file_unique_id}`")

    elif replied_message.document:
        print("File Unique ID:", replied_message.document.file_unique_id)
        print("File ID:", replied_message.document.file_id)
        await msg.reply(f"📂 Document File Unique ID: `{replied_message.document.file_unique_id}`")

    else:
        await msg.reply("❌ Please reply to a video or document file!")

