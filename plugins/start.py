from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


@Client.on_message(filters.command("start"))
async def start(bot, msg):
    try :
        keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📢 Join Channel", url="https://t.me/BlazingSquad")],
         [InlineKeyboardButton("Your Stats", callback_data='stats')]])
        await msg.reply("👋 Welcome! Send me a video, and I'll upload it to MeHub.", reply_markup=keyboard)
    except Exception as e :
        print(e)
