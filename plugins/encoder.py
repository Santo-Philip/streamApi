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
        # Initial message with download progress placeholder (if applicable)
        base_message = "📥 **Download Complete**\n🚀 **Encoding Started... [----------] 0%**"
        await progress_message.edit_text(base_message)
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
            logger.info(f"Running FFmpeg command: {video_cmd}")
            video_process = await asyncio.create_subprocess_shell(
                video_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Progress bar update task
            async def update_progress():
                ESTIMATED_DURATION = 60  # Adjust based on typical video length
                while video_process.returncode is None:
                    await asyncio.sleep(1)  # Faster updates for smoother bar
                    elapsed = time.time() - start_time
                    progress = min(100, int((elapsed / ESTIMATED_DURATION) * 100))
                    bar = "█" * (progress // 10) + "-" * (10 - progress // 10)
                    await progress_message.edit_text(f"{base_message}\n⏳ **Progress:** [{bar}] {progress}%")
                # Ensure 100% is shown before completion
                await progress_message.edit_text(f"{base_message}\n⏳ **Progress:** [██████████] 100%")

            progress_task = asyncio.create_task(update_progress())
            stdout, stderr = await video_process.communicate()
            await video_process.wait()
            await progress_task  # Wait for progress to finish

            if video_process.returncode != 0:
                raise RuntimeError(f"Video encoding failed: {stderr.decode()}")

            logger.info("Encoding completed successfully")
            await progress_message.edit_text(f"{base_message}\n⏳ **Progress:** [██████████] 100%\n🚀 **Encoding Complete! Finalizing...**")

            # Move HLS files to permanent location
            unique_id = str(uuid.uuid4())
            stream_dir = f"streams/{unique_id}"
            os.makedirs(stream_dir, exist_ok=True)
            logger.info(f"Moving {hls_dir} to {stream_dir}")
            shutil.move(hls_dir, stream_dir)
            logger.info(f"Files moved to {stream_dir}")

            # Verify files exist
            output_file = f"{stream_dir}/video/output.m3u8"
            if not os.path.exists(output_file):
                raise FileNotFoundError(f"HLS output missing after move: {output_file}")

            # Insert into database
            file_size = os.path.getsize(file_path)
            logger.info(f"Inserting video data into database: {file_id}, {file_name}, {unique_id}")
            insert_video(msg, file_id, file_name, unique_id)

            await progress_message.edit_text(
                f"{base_message}\n"
                f"⏳ **Progress:** [██████████] 100%\n"
                "✨ **Encoding Complete! 🎬**\n\n"
                f"**📌 Filename:** `{file_name}`\n"
                f"**💾 Size:** `{round(file_size / (1024 * 1024), 2)} MB`\n"
                f"**🔗 Stream Now:** [Watch Here](https://media.mehub.in/video/{unique_id})\n\n"
                "🚀 **Enjoy your video!** 🎉"
            )

            # No removal of original file
            logger.info(f"Keeping original file: {file_path}")

        except Exception as e:
            logger.error(f"Error during encoding: {str(e)}")
            await progress_message.edit_text(
                f"{base_message}\n"
                f"❌ **Encoding Failed!**\n\n"
                f"⚠️ Error: `{str(e)}`\n"
                "🔄 Retrying might help or check file format."
            )
            if os.path.exists(hls_dir):
                logger.info(f"Cleaning up failed HLS dir: {hls_dir}")
                shutil.rmtree(hls_dir, ignore_errors=True)
            # Keep original file even on failure

        que.task_done()