import asyncio
import os
import shutil
import logging
import uuid
import time
import shlex
import json

from pyrogram.errors import MessageNotModified

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

        logger.info(f"Processing file: {file_path}")
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

            # Probe input file for stream info
            probe_cmd = f'ffprobe -v error -show_entries stream=index,codec_type,codec_name -of json {shlex.quote(file_path)}'
            probe_process = await asyncio.create_subprocess_shell(
                probe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            probe_stdout, probe_stderr = await probe_process.communicate()
            if probe_process.returncode != 0:
                raise RuntimeError(f"FFprobe failed: {probe_stderr.decode()}")
            probe_data = json.loads(probe_stdout.decode())
            streams = probe_data['streams']
            video_codec = next((s['codec_name'] for s in streams if s['codec_type'] == 'video'), None)
            audio_streams = [(s['index'], s['codec_name']) for s in streams if s['codec_type'] == 'audio']
            subtitle_streams = [(s['index'], s['codec_name']) for s in streams if s['codec_type'] == 'subtitle']
            logger.info(f"Detected {len(audio_streams)} audio streams and {len(subtitle_streams)} subtitle streams")

            # Determine encoding settings
            video_copy = video_codec in ['h264']
            audio_copies = [codec in ['aac'] for _, codec in audio_streams]
            video_cmd_parts = [f'ffmpeg -hide_banner -y -i {shlex.quote(file_path)}']

            # Video mapping
            video_cmd_parts.append('-map 0:v')
            if video_copy:
                video_cmd_parts.append('-c:v copy')
            else:
                video_cmd_parts.append('-c:v libx264 -preset veryfast')

            # Audio mapping
            audio_map = []
            for i, (idx, codec) in enumerate(audio_streams):
                audio_map.append(f"a:{i}")
                video_cmd_parts.append(f'-map 0:a:{i}')
                if codec in ['aac']:
                    video_cmd_parts.append(f'-c:a:{i} copy')
                else:
                    video_cmd_parts.append(f'-c:a:{i} aac')

            # HLS settings
            video_cmd_parts.extend([
                '-hls_time 5 -hls_list_size 0 -f hls',
                f'-var_stream_map "v:0 {",".join(audio_map)}"',
                f'-master_pl_name master.m3u8',
                f'-hls_segment_filename {shlex.quote(f"{hls_dir}/v%v/segment%d.ts")}',
                f'{shlex.quote(f"{hls_dir}/v%v/playlist.m3u8")}'
            ])
            video_cmd = ' '.join(video_cmd_parts)
            logger.info(f"Running FFmpeg video/audio command: {video_cmd}")
            video_process = await asyncio.create_subprocess_shell(
                video_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            async def process_ffmpeg_output():
                duration = None
                last_update = 0
                stderr_output = []
                stdout_output = []

                # Read stderr for progress
                while True:
                    line = await video_process.stderr.readline()
                    if not line and video_process.returncode is not None:
                        break
                    if line:
                        stderr_line = line.decode().strip()
                        stderr_output.append(stderr_line)
                        if "Duration" in stderr_line and not duration:
                            parts = stderr_line.split("Duration: ")[1].split(",")[0]
                            h, m, s = map(float, parts.split(":"))
                            duration = h * 3600 + m * 60 + s
                            logger.info(f"Detected duration: {duration} seconds")
                        current_time = time.time()
                        if "time=" in stderr_line and duration:
                            time_str = stderr_line.split("time=")[1].split(" ")[0]
                            h, m, s = map(float, time_str.split(":"))
                            processed_time = h * 3600 + m * 60 + s
                            progress = min(100, int((processed_time / duration) * 100))
                            if current_time - last_update >= 3:  # Update every 3 seconds
                                bar = "█" * (progress // 10) + "-" * (10 - progress // 10)
                                await progress_message.edit_text(f"{base_message}\n⏳ **Progress:** [{bar}] {progress}%")
                                last_update = current_time
                        elif current_time - start_time > 1 and current_time - last_update >= 3:  # Fallback for copy
                            elapsed = current_time - start_time
                            progress = min(100, int((elapsed / 10) * 100))  # Assume 10s for copy
                            bar = "█" * (progress // 10) + "-" * (10 - progress // 10)
                            await progress_message.edit_text(f"{base_message}\n⏳ **Progress:** [{bar}] {progress}%")
                            last_update = current_time

                # Read remaining stdout
                while True:
                    line = await video_process.stdout.readline()
                    if not line:
                        break
                    stdout_output.append(line.decode().strip())

                # Wait for process to complete and check return code
                await video_process.wait()
                if video_process.returncode != 0:
                    error_msg = "\n".join(stderr_output) if stderr_output else "Unknown FFmpeg error"
                    raise RuntimeError(f"Video/audio processing failed: {error_msg}")

                # Final progress update
                await progress_message.edit_text(f"{base_message}\n⏳ **Progress:** [██████████] 100%")
                return "\n".join(stdout_output), "\n".join(stderr_output)

            # Run FFmpeg and monitor output
            progress_task = asyncio.create_task(process_ffmpeg_output())
            stdout, stderr = await progress_task
            logger.info(f"FFmpeg stdout: {stdout}")
            logger.info(f"FFmpeg stderr: {stderr}")

            # Extract and convert subtitles
            for idx, (sub_idx, sub_codec) in enumerate(subtitle_streams):
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

            # Update master playlist with subtitles
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

            logger.info("Processing completed successfully")

            file_size = os.path.getsize(file_path)
            logger.info(f"Inserting video data into database: {file_id}, {file_name}, {unique_id}")
            insert_video(msg, file_id, file_name, unique_id)

            await progress_message.edit_text(
                f"{base_message}\n"
                f"⏳ **Progress:** [██████████] 100%\n"
                "✨ **Processing Complete! 🎬**\n\n"
                f"**📌 Filename:** `{file_name}`\n"
                f"**💾 Size:** `{round(file_size / (1024 * 1024), 2)} MB`\n"
                f"**🔗 Stream Now:** [Watch Here](https://media.mehub.in/video/{unique_id})\n\n"
                f"**🎙️ Audio Tracks:** {len(audio_streams)}\n"
                f"**📝 Subtitles:** {len(subtitle_streams)}\n"
                "🚀 **Enjoy your video!** 🎉"
            )

            logger.info(f"Keeping original file: {file_path}")
            logger.info(f"HLS files retained in: {hls_dir}")
        except MessageNotModified as s:
            print(s)
        except Exception as e:
            logger.error(f"Error during processing: {str(e)}")
            if 'progress_task' in locals():
                progress_task.cancel()
            await progress_message.edit_text(
                f"{base_message}\n"
                f"❌ **Processing Failed!**\n\n"
                f"⚠️ Error: `{str(e)}`\n"
                "🔄 Retrying might help or check file format."
            )
            if os.path.exists(hls_dir):
                logger.info(f"Cleaning up failed HLS dir: {hls_dir}")
                shutil.rmtree(hls_dir, ignore_errors=True)

        que.task_done()