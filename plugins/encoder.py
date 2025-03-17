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
        os.makedirs(f"{hls_dir}/video", exist_ok=True)

        if not progress_message:
            logger.warning("No progress message provided, skipping task")
            que.task_done()
            continue

        await progress_message.edit_text("🚀 Encoding Started... [0%]")

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
        is_aac = "aac" in stderr_str.lower()

        # Step 1: Copy video stream without audio
        video_cmd = (
            f'ffmpeg -hide_banner -y -i "{file_path}" '
            f'-map 0:v -c:v copy -an '
            f'-hls_time 5 -hls_list_size 0 '
            f'-hls_segment_filename "{hls_dir}/video/segment%d.ts" '
            f'"{hls_dir}/video/output.m3u8"'
        )
        logger.info(f"Running video FFmpeg command: {video_cmd}")
        video_process = await asyncio.create_subprocess_shell(video_cmd)
        await video_process.communicate()

        # Step 2: Extract and align each audio track
        audio_playlists = []
        for i in range(audio_count):
            audio_dir = f"{hls_dir}/audio_{i}"
            os.makedirs(audio_dir, exist_ok=True)

            audio_cmd = (
                f'ffmpeg -hide_banner -y -i "{file_path}" '
                f'-map 0:v -map 0:a:{i} -c:v copy -c:a {"copy" if is_aac else "aac"} '
                f'-hls_time 5 -hls_list_size 0 '
                f'-hls_segment_filename "{audio_dir}/segment%d.ts" '
                f'"{audio_dir}/output.m3u8"'
            )
            logger.info(f"Running audio FFmpeg command {i}: {audio_cmd}")
            audio_process = await asyncio.create_subprocess_shell(audio_cmd)
            await audio_process.communicate()
            audio_playlists.append((i, languages[i % len(languages)], audio_dir))

        # Step 3: Generate master playlist
        master_playlist = "#EXTM3U\n#EXT-X-VERSION:3\n"
        for i, lang, audio_dir in audio_playlists:
            default = "YES" if i == 0 else "NO"
            master_playlist += (
                f'#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="{lang.capitalize()}",'
                f'LANGUAGE="{lang}",DEFAULT={default},AUTOSELECT=YES,URI="audio_{i}/output.m3u8"\n'
            )
        master_playlist += (
            f'#EXT-X-STREAM-INF:BANDWIDTH=2000000,AUDIO="audio"\n'
            f'video/output.m3u8\n'
        )

        with open(f"{hls_dir}/master.m3u8", "w") as f:
            f.write(master_playlist)

        await progress_message.edit_text(
            f"✨ Encoding Complete! 🎉\n\n🌐 [Watch Here](https://media.mehub.in/video/{file_id})")
        insert_video(msg, file_id, file_name, str(uuid.uuid4()))

        que.task_done()
