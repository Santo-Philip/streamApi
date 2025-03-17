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

        await progress_message.edit_text("🚀 **Encoding Started... [0%]**")

        try:
            # Check if FFmpeg is installed
            ffmpeg_check = await asyncio.create_subprocess_shell(
                "ffmpeg -version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await ffmpeg_check.communicate()
            if ffmpeg_check.returncode != 0:
                raise RuntimeError(f"FFmpeg not found or failed: {stderr.decode()}")

            # Verify input file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Input file not found: {file_path}")

            # Get audio track info
            process = await asyncio.create_subprocess_shell(
                f'ffmpeg -i "{file_path}" -f null -',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            stderr_str = stderr.decode()
            audio_count = stderr_str.count("Audio:")
            is_aac = "aac" in stderr_str.lower()

            # Step 1: Copy video stream
            video_cmd = (
                f'ffmpeg -hide_banner -y -i "{file_path}" '
                f'-map 0:v -c:v copy -an '
                f'-hls_time 5 -hls_list_size 0 '
                f'-hls_segment_filename "{hls_dir}/video/segment%d.ts" '
                f'"{hls_dir}/video/output.m3u8"'
            )
            video_process = await asyncio.create_subprocess_shell(
                video_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            audio_playlists = []
            for i in range(audio_count):
                audio_dir = f"{hls_dir}/audio_{i}"
                os.makedirs(audio_dir, exist_ok=True)
                audio_cmd = (
                    f'ffmpeg -hide_banner -y -i "{file_path}" '
                    f'-map 0:a:{i} '
                    f'-c:a {"copy" if is_aac else "aac"} -b:a 128k '
                    f'-hls_time 5 -hls_list_size 0 '
                    f'-hls_segment_filename "{audio_dir}/segment%d.ts" '
                    f'"{audio_dir}/output.m3u8"'
                )
                audio_process = await asyncio.create_subprocess_shell(
                    audio_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await audio_process.communicate()
                if audio_process.returncode == 0:
                    audio_playlists.append(f'audio_{i}/output.m3u8')

            master_playlist = "#EXTM3U\n#EXT-X-VERSION:3\n"
            for i, audio in enumerate(audio_playlists):
                master_playlist += (
                    f'#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="Track {i + 1}",DEFAULT={"YES" if i == 0 else "NO"},AUTOSELECT=YES,URI="{audio}"
                    '
                )
            master_playlist += f'#EXT-X-STREAM-INF:BANDWIDTH=2000000,AUDIO="audio"\nvideo/output.m3u8\n'

            with open(f"{hls_dir}/master.m3u8", "w") as f:
                f.write(master_playlist)

            await progress_message.edit_text("🚀 **Encoding Complete! Finalizing...**")

            file_size = os.path.getsize(file_path)
            unique_id = str(uuid.uuid4())
            insert_video(msg, file_id, file_name, unique_id)

            await progress_message.edit_text(
                "✨ **Encoding Complete! 🎬**\n\n"
                f"**📌 Filename:** `{file_name}`\n"
                f"**💾 Size:** `{round(file_size / (1024 * 1024), 2)} MB`\n"
                f"**🔗 Stream Now:** [Watch Here](https://media.mehub.in/video/{unique_id})\n\n"
                "🚀 **Enjoy your video!** 🎉"
            )

        except Exception as e:
            logger.error(f"Error during encoding: {str(e)}")
            await progress_message.edit_text(f"❌ **Encoding Failed!**\n\n⚠️ Error: `{str(e)}`")

        finally:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                if os.path.exists(hls_dir):
                    shutil.rmtree(hls_dir, ignore_errors=True)
            except Exception as cleanup_error:
                logger.error(f"Cleanup failed: {cleanup_error}")

        que.task_done()