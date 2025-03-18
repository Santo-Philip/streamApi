import asyncio
import os
import shutil
import logging
import uuid
import time
import shlex
import json
import subprocess
from database.video import insert_video
from plugins.video import que
from pyrogram.errors import MessageNotModified

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

        # Define directory for original files
        originals_dir = os.path.join(os.getcwd(), "originals")
        os.makedirs(originals_dir, exist_ok=True)

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
        base_message = "📥 **Download Complete**\n⏳ **Progress:** [██████████] 100%**\n\n🚀 Encoding Started..."
        await progress_message.edit_text(base_message)
        start_time = time.time()

        try:
            ffmpeg_check = subprocess.run("ffmpeg -version", shell=True, capture_output=True, text=True)
            if ffmpeg_check.returncode != 0:
                raise RuntimeError(f"FFmpeg not found: {ffmpeg_check.stderr}")

            probe_cmd = f'ffprobe -v error -show_entries stream=index,codec_type,codec_name,sample_rate,channels -of json {shlex.quote(file_path)}'
            probe_process = subprocess.run(probe_cmd, shell=True, capture_output=True, text=True)
            if probe_process.returncode != 0:
                raise RuntimeError(f"FFprobe failed: {probe_process.stderr}")
            probe_data = json.loads(probe_process.stdout)
            streams = probe_data['streams']
            video_codec = next((s['codec_name'] for s in streams if s['codec_type'] == 'video'), None)
            audio_streams = [(s['index'], s['codec_name'], s.get('sample_rate', 'N/A'), s.get('channels', 'N/A'))
                             for s in streams if s['codec_type'] == 'audio']
            subtitle_streams = [(s['index'], s['codec_name']) for s in streams if s['codec_type'] == 'subtitle']
            logger.info(f"Video codec: {video_codec}")
            for idx, codec, sample_rate, channels in audio_streams:
                logger.info(f"Audio stream {idx}: codec={codec}, sample_rate={sample_rate}, channels={channels}")
            logger.info(f"Detected {len(audio_streams)} audio streams and {len(subtitle_streams)} subtitle streams")

            # Determine encoding settings
            video_copy = video_codec in ['h264']
            audio_copies = [codec in ['aac'] for _, codec, _, _ in audio_streams]
            video_cmd_parts = [f'ffmpeg -hide_banner -y -i {shlex.quote(file_path)}']

            # Video mapping (output to video_subdir)
            video_cmd_parts.append('-map 0:v')
            if video_copy:
                video_cmd_parts.append('-c:v copy')
            else:
                video_cmd_parts.append('-c:v libx264 -preset veryfast')
            video_cmd_parts.extend([
                f'-hls_time 5 -hls_list_size 0 -f hls',
                f'-hls_segment_filename {shlex.quote(f"{video_subdir}/segment%d.ts")}',
                f'{shlex.quote(f"{video_subdir}/playlist.m3u8")}'
            ])

            # Audio mapping (output to audio_subdir)
            audio_cmd_parts = [f'ffmpeg -hide_banner -y -i {shlex.quote(file_path)}']
            for i, (idx, codec, sample_rate, channels) in enumerate(audio_streams):
                audio_cmd_parts.append(f'-map 0:a:{i}')
                if codec in ['aac']:
                    audio_cmd_parts.append(f'-c:a:{i} copy')
                else:
                    audio_cmd_parts.append(f'-c:a:{i} aac -profile:a:{i} aac_low -ar:a:{i} 44100 -ac:a:{i} 2')
            audio_cmd_parts.extend([
                '-vn',  # No video in audio stream
                f'-hls_time 5 -hls_list_size 0 -f hls',
                f'-hls_segment_filename {shlex.quote(f"{audio_subdir}/segment%d.ts")}',
                f'{shlex.quote(f"{audio_subdir}/playlist.m3u8")}'
            ])

            # Run FFmpeg commands
            video_cmd = ' '.join(video_cmd_parts)
            audio_cmd = ' '.join(audio_cmd_parts)
            logger.info(f"Running FFmpeg video command: {video_cmd}")
            logger.info(f"Running FFmpeg audio command: {audio_cmd}")

            # Video process
            video_process = subprocess.Popen(
                video_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Audio process (only if audio streams exist)
            audio_process = None
            if audio_streams:
                audio_process = subprocess.Popen(
                    audio_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )

            async def process_ffmpeg_output(process, stream_type="video"):
                duration = None
                last_update = 0
                stderr_output = []
                last_progress = -1

                while process.poll() is None:
                    line = process.stderr.readline().strip()
                    if line:
                        stderr_output.append(line)
                        if "Duration" in line and not duration:
                            parts = line.split("Duration: ")[1].split(",")[0]
                            h, m, s = map(float, parts.split(":"))
                            duration = h * 3600 + m * 60 + s
                            logger.info(f"Detected {stream_type} duration: {duration} seconds")
                        current_time = time.time()
                        if "time=" in line and duration:
                            time_str = line.split("time=")[1].split(" ")[0]
                            h, m, s = map(float, time_str.split(":"))
                            processed_time = h * 3600 + m * 60 + s
                            progress = min(100, int((processed_time / duration) * 100))
                            if current_time - last_update >= 3 and progress != last_progress:
                                bar = "█" * (progress // 10) + "-" * (10 - progress // 10)
                                try:
                                    await progress_message.edit_text(
                                        f"{base_message}\n⏳ **{stream_type.capitalize()} Progress:** [{bar}] {progress}%")
                                    last_update = current_time
                                    last_progress = progress
                                except MessageNotModified:
                                    pass
                        elif current_time - start_time > 1 and current_time - last_update >= 3:
                            elapsed = current_time - start_time
                            progress = min(100, int((elapsed / 10) * 100))
                            if progress != last_progress:
                                bar = "█" * (progress // 10) + "-" * (10 - progress // 10)
                                try:
                                    await progress_message.edit_text(
                                        f"{base_message}\n⏳ **{stream_type.capitalize()} Progress:** [{bar}] {progress}%")
                                    last_update = current_time
                                    last_progress = progress
                                except MessageNotModified:
                                    pass
                    await asyncio.sleep(0.1)

                stderr_remaining = process.stderr.read()
                if stderr_remaining:
                    stderr_output.append(stderr_remaining.strip())
                stdout_output = process.stdout.read().strip()

                return_code = process.wait()
                if return_code != 0:
                    error_msg = "\n".join(stderr_output) if stderr_output else f"Unknown FFmpeg {stream_type} error"
                    raise RuntimeError(f"{stream_type.capitalize()} processing failed: {error_msg}")

                if last_progress != 100:
                    await progress_message.edit_text(
                        f"{base_message}\n⏳ **{stream_type.capitalize()} Progress:** [██████████] 100%")
                return stdout_output, "\n".join(stderr_output)

            # Run FFmpeg processes and monitor output
            video_task = asyncio.create_task(process_ffmpeg_output(video_process, "video"))
            audio_task = asyncio.create_task(process_ffmpeg_output(audio_process, "audio")) if audio_process else None

            video_stdout, video_stderr = await video_task
            logger.info(f"FFmpeg video stdout: {video_stdout}")
            logger.info(f"FFmpeg video stderr: {video_stderr}")

            if audio_task:
                audio_stdout, audio_stderr = await audio_task
                logger.info(f"FFmpeg audio stdout: {audio_stdout}")
                logger.info(f"FFmpeg audio stderr: {audio_stderr}")

            # Extract and convert subtitles
            for idx, (sub_idx, sub_codec) in enumerate(subtitle_streams):
                sub_cmd = (
                    f'ffmpeg -hide_banner -y -i {shlex.quote(file_path)} '
                    f'-map 0:s:{idx} -c:s webvtt '
                    f'{shlex.quote(f"{subtitle_subdir}/sub_{idx}.vtt")}'
                )
                logger.info(f"Extracting subtitle {idx}: {sub_cmd}")
                sub_process = subprocess.run(
                    sub_cmd,
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if sub_process.returncode != 0:
                    logger.warning(f"Subtitle {idx} extraction failed: {sub_process.stderr}")

            # Generate master playlist
            master_file = f"{hls_dir}/master.m3u8"
            with open(master_file, 'w') as f:
                f.write('#EXTM3U\n#EXT-X-VERSION:3\n')
                if audio_streams:
                    f.write(
                        '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="Audio 0",DEFAULT=YES,URI="audio/playlist.m3u8"\n')
                for idx in range(len(subtitle_streams)):
                    if os.path.exists(f"{subtitle_subdir}/sub_{idx}.vtt"):
                        f.write(
                            f'#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="Subtitle {idx}",DEFAULT={"YES" if idx == 0 else "NO"},URI="subtitles/sub_{idx}.vtt"\n')
                f.write('#EXT-X-STREAM-INF:BANDWIDTH=5000000,AUDIO="audio",SUBTITLES="subs"\n')
                f.write('video/playlist.m3u8\n')

            with open(master_file, 'r') as f:
                logger.info(f"Master playlist content:\n{f.read()}")

            logger.info("Processing completed successfully")

            file_size = os.path.getsize(file_path)
            logger.info(f"Inserting video data into database: {file_id}, {file_name}, {unique_id}")
            insert_video(msg, file_id, file_name, unique_id)

            # Rename and move the original file
            original_extension = os.path.splitext(file_path)[1]  # Get the file extension (e.g., .mp4)
            new_file_name = f"{file_id}{original_extension}"
            new_file_path = os.path.join(originals_dir, new_file_name)

            try:
                shutil.move(file_path, new_file_path)
                logger.info(f"Renamed and moved original file from {file_path} to {new_file_path}")
            except Exception as e:
                logger.error(f"Failed to rename/move original file {file_path} to {new_file_path}: {str(e)}")
                # Optionally, you could copy instead of move and delete the original if move fails
                shutil.copy2(file_path, new_file_path)
                os.remove(file_path)
                logger.info(f"Copied and deleted original file as fallback: {new_file_path}")

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

            logger.info(f"Original file renamed and stored as: {new_file_path}")
            logger.info(f"HLS files retained in: {hls_dir}")

        except Exception as e:
            logger.error(f"Error during processing: {str(e)}")
            if 'video_task' in locals():
                video_task.cancel()
            if 'audio_task' in locals() and audio_task:
                audio_task.cancel()
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