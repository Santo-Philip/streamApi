import asyncio
import os
import shutil
from database.video import insert_video
from plugins.video import que


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
            que.task_done()
            continue  # Skip if progress message is missing

        await progress_message.edit_text("🚀 Encoding Started... [0%]")

        # FFmpeg command to generate HLS files
        cmd = (
            f'ffmpeg -hide_banner -y -i "{file_path}" '
            f'-c:v copy -c:a copy -hls_time 5 -hls_list_size 0 '
            f'-progress pipe:1 '
            f'"{hls_dir}/output.m3u8"'
        )

        process = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        while process.returncode is None:  # Keep checking progress while FFmpeg is running
            await asyncio.sleep(2)  # Wait 2 seconds before checking progress

            # Count the number of .ts files generated so far
            ts_files = [f for f in os.listdir(hls_dir) if f.endswith(".ts")]
            segment_count = len(ts_files)

            # Estimate progress (Assume 100 segments for a full-length video)
            progress = min(100, int((segment_count / 100) * 100))
            bar = "█" * (progress // 5) + " " * (20 - (progress // 5))  # 20-block bar

            try:
                await progress_message.edit_text(f"🚀 Encoding... \n\n[{bar}] {progress}%")
            except Exception:
                pass  # Prevent crashes if the message cannot be edited

        await process.wait()

        if process.returncode == 0:
            file_size = os.path.getsize(file_path)
            await progress_message.edit_text(
                "✅ **Encoding Complete!** 🎉\n\n"
                "🔹 **Progress:** `[████████████████████]` **100%**\n"
                f"🔹 **Filename:** `{file_name}`\n"
                f"🔹 **Size:** `{round(file_size / (1024 * 1024), 2)} MB`\n\n"
                "⚡ **Completed...**"
            )
            insert_video(msg, file_id, file_name)
        else:
            await progress_message.edit_text("❌ Encoding Failed! Cleaning up files...")

            # Ensure cleanup of the video file and folder
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                if os.path.exists(hls_dir):
                    shutil.rmtree(hls_dir, ignore_errors=True)
            except Exception as e:
                await progress_message.edit_text(f"⚠️ Cleanup Error: {e}")

        que.task_done()
