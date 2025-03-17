import asyncio
import os
import shutil
import logging
import uuid
import time
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
        video_subdir = f"{hls_dir}/video"
        os.makedirs(video_subdir, exist_ok=True)

        if not progress_message:
            logger.warning("No progress message provided, skipping task")
            await progress_message.edit_text("❌ **Error:** No progress message provided!")
            que.task_done()
            continue

        if not os.path.exists(file_path):
            logger.error(f"File missing before encoding: {file_path}")
            await progress_message.edit_text("❌ **Error:** Input file missing!")
            que.task_done()
            continue

        logger.info(f"Encoding file: {file_path}")
        await progress_message.edit_text("🚀 **Encoding Started... [----------] 0%**")
        start_time = time.time()

        try:
            # Check FFmpeg
            ffmpeg_check = await asyncio.create_subprocess_shell(
                "ffmpeg -version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await ffmpeg_check.communicate()
            if ffmpeg_check.returncode != 0:
                raise RuntimeError(f"FFmpeg not found: {stderr.decode()}")

            # Encode video
            video_cmd = (
                f'ffmpeg -hide_banner -y -i "{file_path}" '
                f'-map 0:v -c:v copy -an '
                f'-hls_time 5 -hls_list_size 0 '
                f'-hls_segment_filename "{video_subdir}/segment%d.ts" '
                f'"{hls_dir}/video/output.m3u8"'
            )
            video_process = await asyncio.create_subprocess_shell(
                video_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Progress bar update task (simulated progress)
            async def update_progress():
                # Simulate progress based on elapsed time (adjust ESTIMATED_DURATION as needed)
                ESTIMATED_DURATION = 60  # Placeholder: estimate encoding time in seconds
                while video_process.returncode is None:
                    await asyncio.sleep(3)
                    elapsed = time.time() - start_time
                    progress = min(100, int((elapsed / ESTIMATED_DURATION) * 100))
                    bar = "█" * (progress // 10) + "-" * (10 - progress // 10)
                    await progress_message.edit_text(f"🚀 **Encoding in Progress... [{bar}] {progress}%**")

            asyncio.create_task(update_progress())
            stdout, stderr = await video_process.communicate()
            await video_process.wait()

            if video_process.returncode != 0:
                raise RuntimeError(f"Video encoding failed: {stderr.decode()}")

            await progress_message.edit_text("🚀 **Encoding Complete! Finalizing...**")

            file_size = os.path.getsize(file_path)
            unique_id = str(uuid.uuid4())
            insert_video(msg, file_id, file_name, unique_id)

            # Move HLS files to a permanent location (e.g., 'streams' directory)
            stream_dir = f"streams/{unique_id}"
            os.makedirs(stream_dir, exist_ok=True)
            shutil.move(hls_dir, stream_dir)

            await progress_message.edit_text(
                "✨ **Encoding Complete! 🎬**\n\n"
                f"**📌 Filename:** `{file_name}`\n"
                f"**💾 Size:** `{round(file_size / (1024 * 1024), 2)} MB`\n"
                f"**🔗 Stream Now:** [Watch Here](https://media.mehub.in/video/{unique_id})\n\n"
                "🚀 **Enjoy your video!** 🎉"
            )

            # Optional: Clean up original file only (keep HLS files for streaming)
            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            logger.error(f"Error during encoding: {str(e)}")
            await progress_message.edit_text(
                "❌ **Encoding Failed!**\n\n"
                f"⚠️ Error: `{str(e)}`\n"
                "🔄 Retrying might help or check file format."
            )
            # Clean up on failure
            if os.path.exists(hls_dir):
                shutil.rmtree(hls_dir, ignore_errors=True)
            if os.path.exists(file_path):
                os.remove(file_path)

        que.task_done()
