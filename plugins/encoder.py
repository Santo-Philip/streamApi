import asyncio
import os
import shutil
import logging
import uuid
from database.video import insert_video
from plugins.video import que

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def encode_video():
    while True:
        video_data = await que.get()
        file_path = video_data["file_path"]
        chat_id = video_data["chat_id"]
        file_name = video_data["file_name"]
        bot = video_data["bot"]
        file_id = video_data["file_id"]
        progress_message = video_data['progress']
        msg = video_data['msg']

        file_path = os.path.abspath(file_path)
        hls_dir = f"downloads/{file_id}"
        os.makedirs(hls_dir, exist_ok=True)

        if not progress_message:
            logger.warning("No progress message provided, skipping task")
            que.task_done()
            continue

        await progress_message.edit_text("🚀 Encoding Started... [0%]")

        # Check if FFmpeg is installed
        ffmpeg_check = await asyncio.create_subprocess_shell(
            "ffmpeg -version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await ffmpeg_check.communicate()
        if ffmpeg_check.returncode != 0:
            await progress_message.edit_text(f"❌ FFmpeg not found or failed: {stderr.decode()}")
            que.task_done()
            continue

        # Verify input file exists
        if not os.path.exists(file_path):
            await progress_message.edit_text(f"❌ Input file not found: {file_path}")
            que.task_done()
            continue

        # FFmpeg command to use only the default audio track
        cmd = (
            f'ffmpeg -hide_banner -y -i "{file_path}" '
            f'-map 0:v -map 0:a:0 '  # Map video and only the default audio track
            f'-c:v libx264 -c:a aac -b:a 192k '  # Re-encode to H.264/AAC
            f'-hls_time 5 -hls_list_size 0 '
            f'-hls_segment_filename "{hls_dir}/segment%d.ts" '
            f'-progress pipe:1 '
            f'"{hls_dir}/output.m3u8"'
        )
        logger.info(f"Running FFmpeg command: {cmd}")

        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Progress tracking
        while process.returncode is None:
            await asyncio.sleep(2)
            ts_files = [f for f in os.listdir(hls_dir) if f.endswith(".ts")]
            segment_count = len(ts_files)
            progress = min(100, int((segment_count / 100) * 100))  # Adjust divisor if needed
            bar = "█" * (progress // 5) + " " * (20 - (progress // 5))
            try:
                await progress_message.edit_text(f"🚀 Encoding... \n\n[{bar}] {progress}%")
            except Exception:
                pass

        stdout, stderr = await process.communicate()
        return_code = process.returncode

        unique_id = str(uuid.uuid4())
        if return_code == 0:
            file_size = os.path.getsize(file_path)
            await progress_message.edit_text(
                "✨ **Encoding Masterpiece Complete!** 🎉\n\n"
                "📊 **Progress:** `[███████████]` **100%**\n"
                f"🎬 **Filename:** `{file_name}`\n"
                f"💾 **Size:** `{round(file_size / (1024 * 1024), 2)} MB`\n"
                f"🌐 **Stream Now:** [Watch Here](https://media.mehub.in/video/{unique_id})\n\n"
                "⚡ **Ready to Enjoy!** 🚀"
            )
            insert_video(msg, file_id, file_name, unique_id)
        else:
            error_message = stderr.decode() if stderr else "Unknown error"
            await progress_message.edit_text(f"❌ Encoding Failed!\n\nError: {error_message}")
            logger.error(f"FFmpeg failed with code {return_code}: {error_message}")

            # Cleanup on failure
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                if os.path.exists(hls_dir):
                    shutil.rmtree(hls_dir, ignore_errors=True)
            except Exception as e:
                await progress_message.edit_text(f"⚠️ Cleanup Error: {e}")
                logger.error(f"Cleanup failed: {e}")

        que.task_done()