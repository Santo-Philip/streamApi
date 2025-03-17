import asyncio
import os
import shutil
import logging
import uuid
import time
import shlex
from database.video import insert_video
from plugins.video import que

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
        unique_id = str(uuid.uuid4())
        file_path = os.path.abspath(file_path)
        hls_dir = f"downloads/{file_id}"
        video_subdir = f"{hls_dir}/video"
        audio_subdir = f"{hls_dir}/audio"
        subtitle_subdir = f"{hls_dir}/subtitles"
        os.makedirs(video_subdir, exist_ok=True)
        os.makedirs(audio_subdir, exist_ok=True)
        os.makedirs(subtitle_subdir, exist_ok=True)

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

            # Step 1: Probe the input file for stream info
            probe_cmd = f'ffprobe -v error -show_entries stream=index,codec_type -of json {shlex.quote(file_path)}'
            probe_process = await asyncio.create_subprocess_shell(
                probe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            probe_stdout, probe_stderr = await probe_process.communicate()
            if probe_process.returncode != 0:
                raise RuntimeError(f"FFprobe failed: {probe_stderr.decode()}")
            import json
            probe_data = json.loads(probe_stdout.decode())
            audio_streams = [s['index'] for s in probe_data['streams'] if s['codec_type'] == 'audio']
            subtitle_streams = [s['index'] for s in probe_data['streams'] if s['codec_type'] == 'subtitle']
            logger.info(f"Detected {len(audio_streams)} audio streams and {len(subtitle_streams)} subtitle streams")

            # Step 2: Encode video and audio to HLS
            video_cmd = (
                f'ffmpeg -hide_banner -y -i {shlex.quote(file_path)} '
                f'-map 0:v -c:v libx264 -preset veryfast '
                f'-map 0:a -c:a aac '
                f'-hls_time 5 -hls_list_size 0 -f hls '
                f'-var_stream_map "v:0 {",".join(f"a:{i}" for i in range(len(audio_streams)))}" '
                f'-master_pl_name master.m3u8 '
                f'-hls_segment_filename {shlex.quote(f"{video_subdir}/v%v/segment%d.ts")} '
                f'{shlex.quote(f"{hls_dir}/v%v/playlist.m3u8")}'
            )
            logger.info(f"Running FFmpeg video/audio command: {video_cmd}")
            video_process = await asyncio.create_subprocess_shell(
                video_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            async def update_progress():
                duration = None
                while video_process.returncode is None:
                    await asyncio.sleep(1)
                    stderr_line = await video_process.stderr.readline()
                    line = stderr_line.decode().strip()
                    if "Duration" in line and not duration:
                        parts = line.split("Duration: ")[1].split(",")[0]
                        h, m, s = map(float, parts.split(":"))
                        duration = h * 3600 + m * 60 + s
                    if duration and "time=" in line:
                        time_str = line.split("time=")[1].split(" ")[0]
                        h, m, s = map(float, time_str.split(":"))
                        current_time = h * 3600 + m * 60 + s
                        progress = min(100, int((current_time / duration) * 100))
                        bar = "█" * (progress // 10) + "-" * (10 - progress // 10)
                        await progress_message.edit_text(f"{base_message}\n⏳ **Progress:** [{bar}] {progress}%")
                    elif elapsed > 1:  # Fallback
                        elapsed = time.time() - start_time
                        progress = min(100, int((elapsed / 60) * 100))
                        bar = "█" * (progress // 10) + "-" * (10 - progress // 10)
                        await progress_message.edit_text(f"{base_message}\n⏳ **Progress:** [{bar}] {progress}%")
                await progress_message.edit_text(f"{base_message}\n⏳ **Progress:** [██████████] 100%")

            progress_task = asyncio.create_task(update_progress())
            stdout, stderr = await video_process.communicate()
            await video_process.wait()
            if video_process.returncode != 0:
                raise RuntimeError(f"Video/audio encoding failed: {stderr.decode()}")
            await progress_task

            logger.info(f"FFmpeg stdout: {stdout.decode()}")
            logger.info(f"FFmpeg stderr: {stderr.decode()}")

            # Step 3: Extract and convert subtitles to WebVTT
            for idx, sub_idx in enumerate(subtitle_streams):
                sub_cmd = (
                    f'ffmpeg -hide_banner -y -i {shlex.quote(file_path)} '
                    f'-map 0:s:{idx} -c:s webvtt '
                    f'{shlex.quote(f"{subtitle_subdir}/sub_{idx}.vtt")}'
                )
                logger.info(f"Extracting subtitle {idx}: {sub_cmd}")
                sub_process = await asyncio.create_subprocess_shell(
                    sub_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                sub_stdout, sub_stderr = await sub_process.communicate()
                if sub_process.returncode != 0:
                    logger.warning(f"Subtitle {idx} extraction failed: {sub_stderr.decode()}")

            # Step 4: Update master playlist with subtitles
            master_file = f"{hls_dir}/master.m3u8"
            if not os.path.exists(master_file):
                raise FileNotFoundError(f"Master playlist not generated: {master_file}")

            with open(master_file, 'a') as f:
                for idx in range(len(subtitle_streams)):
                    if os.path.exists(f"{subtitle_subdir}/sub_{idx}.vtt"):
                        f.write(
                            f'#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="Subtitle {idx}",URI="../subtitles/sub_{idx}.vtt"\n')
                f.write('#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1280x720,SUBTITLES="subs"\n')
                f.write('v0/playlist.m3u8\n')

            logger.info("Encoding and subtitle extraction completed successfully")

            # Step 5: Finalize
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
                f"**🎙️ Audio Tracks:** {len(audio_streams)}\n"
                f"**📝 Subtitles:** {len(subtitle_streams)}\n"
                "🚀 **Enjoy your video!** 🎉"
            )

            logger.info(f"Keeping original file: {file_path}")
            logger.info(f"HLS files retained in: {hls_dir}")

        except Exception as e:
            logger.error(f"Error during encoding: {str(e)}")
            if 'progress_task' in locals():
                progress_task.cancel()
            await progress_message.edit_text(
                f"{base_message}\n"
                f"❌ **Encoding Failed!**\n\n"
                f"⚠️ Error: `{str(e)}`\n"
                "🔄 Retrying might help or check file format."
            )
            if os.path.exists(hls_dir):
                logger.info(f"Cleaning up failed HLS dir: {hls_dir}")
                shutil.rmtree(hls_dir, ignore_errors=True)

        que.task_done()