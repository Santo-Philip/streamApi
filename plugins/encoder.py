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

        # Get audio track info
        process = await asyncio.create_subprocess_shell(
            f'ffmpeg -i "{file_path}" -f null -',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        stderr_str = stderr.decode()
        audio_count = stderr_str.count("Audio:")
        languages = ["eng", "spa", "fre", "ger", "ita"]
        is_aac = "aac" in stderr_str.lower()  # Check if any audio is AAC

        # Step 1: Copy video stream
        video_cmd = (
            f'ffmpeg -hide_banner -y -i "{file_path}" '
            f'-map 0:v -c:v copy '
            f'-an '  # No audio in video stream
            f'-hls_time 5 -hls_list_size 0 '
            f'-hls_segment_filename "{hls_dir}/video/segment%d.ts" '
            f'-progress pipe:1 '
            f'"{hls_dir}/video/output.m3u8"'
        )
        logger.info(f"Running video FFmpeg command: {video_cmd}")
        video_process = await asyncio.create_subprocess_shell(
            video_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        video_stdout, video_stderr = await video_process.communicate()

        # Step 2: Process each audio stream (only up to audio_count)
        audio_playlists = []
        for i in range(audio_count):  # Changed to range(audio_count) to match actual streams
            audio_dir = f"{hls_dir}/audio_{i}"
            os.makedirs(audio_dir, exist_ok=True)
            # Check if audio can be copied (AAC) or needs re-encoding (e.g., Opus)
            audio_cmd = (
                f'ffmpeg -hide_banner -y -i "{file_path}" '
                f'-map 0:a:{i} '
                f'-c:a {"copy" if is_aac else "aac"} -b:a 128k '
                f'-vn '  # No video in audio stream
                f'-hls_time 5 -hls_list_size 0 '
                f'-hls_segment_filename "{audio_dir}/segment%d.ts" '
                f'-progress pipe:1 '
                f'"{audio_dir}/output.m3u8"'
            )
            logger.info(f"Running audio FFmpeg command {i}: {audio_cmd}")
            audio_process = await asyncio.create_subprocess_shell(
                audio_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await audio_process.communicate()
            if audio_process.returncode == 0:
                audio_playlists.append((i, languages[i], audio_dir))
            else:
                logger.error(f"Audio {i} failed: {stderr.decode()}")

        # Step 3: Generate master playlist
        master_playlist = "#EXTM3U\n#EXT-X-VERSION:3\n"
        for i, lang, audio_dir in audio_playlists:
            default = "YES" if i == 0 else "NO"  # First audio as default
            master_playlist += (
                f'#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="{lang.capitalize()}",'
                f'LANGUAGE="{lang}",DEFAULT={default},AUTOSELECT=YES,URI="audio_{i}/output.m3u8"\n'
            )
        master_playlist += (
            f'#EXT-X-STREAM-INF:BANDWIDTH=2000000,AUDIO="audio"\n'
            f'video/output.m3u8\n'
        )

        # Write master playlist
        master_path = f"{hls_dir}/master.m3u8"
        with open(master_path, "w") as f:
            f.write(master_playlist)

        # Progress tracking (simplified to video completion)
        while video_process.returncode is None:
            await asyncio.sleep(2)
            ts_files = [f for f in os.listdir(f"{hls_dir}/video") if f.endswith(".ts")]
            segment_count = len(ts_files)
            progress = min(100, int((segment_count / 100) * 100))
            bar = "█" * (progress // 5) + " " * (20 - (progress // 5))
            try:
                await progress_message.edit_text(f"🚀 Encoding... \n\n[{bar}] {progress}%")
            except Exception:
                pass

        # Check overall success
        if video_process.returncode == 0 and audio_playlists:
            file_size = os.path.getsize(file_path)
            unique_id = str(uuid.uuid4())
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
            error_message = (video_stderr or stderr).decode() if (video_stderr or stderr) else "Unknown error"
            await progress_message.edit_text(f"❌ Encoding Failed!\n\nError: {error_message}")
            logger.error(f"FFmpeg failed: {error_message}")

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