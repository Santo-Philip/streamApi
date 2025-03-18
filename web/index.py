import os
import shutil

from aiohttp import web
from database.spbase import supabase
from datetime import datetime
import pytz
from web.home import logger


async def video_index(request):
    try:
        # Fetch videos from Supabase
        response = supabase.table("stream").select("*").execute()
        videos = response.data if hasattr(response, 'data') else []
        logger.info(f"Number of videos fetched: {len(videos)}")
        if videos:
            logger.info(f"First video data: {videos[0]}")

        # Check template existence
        file_path = os.path.join(os.path.dirname(__file__), "index.html")
        if not os.path.exists(file_path):
            logger.error(f"Template not found at: {file_path}")
            return web.Response(text="Video HTML template not found", status=404)

        # Read template
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Generate video grid
        video_grid = ""
        for i, video in enumerate(videos):
            video_url = video.get('token', '')
            video_id = video.get('video','')
            video_title = video.get('title', 'Untitled')
            created_at = video.get('created_at', 'Unknown')
            user = video.get('user', 'Unknown')

            # Format created_at and calculate hours ago
            if created_at != 'Unknown':
                try:
                    # Parse the created_at as an offset-aware datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

                    # Ensure current time is also offset-aware (UTC)
                    now_utc = datetime.now(pytz.UTC)

                    # Format date and time
                    date_str = dt.strftime("%B %d, %Y")  # e.g., "March 18, 2025"
                    time_str = dt.strftime("%I:%M %p")  # e.g., "03:30 PM"

                    # Calculate hours ago
                    hours_ago = int((now_utc - dt).total_seconds() / 3600)
                    hours_ago_str = f"Just now" if hours_ago == 0 else f"{hours_ago} hour{'s' if hours_ago != 1 else ''} ago"
                except Exception as e:
                    logger.warning(f"Error formatting date for video {video_url}: {e}")
                    date_str = "Unknown Date"
                    time_str = "Unknown Time"
                    hours_ago_str = "Unknown"
            else:
                date_str = "Unknown Date"
                time_str = "Unknown Time"
                hours_ago_str = "Unknown"

            if video_url:
                full_url = f"https://media.mehub.in/video/{video_url}"
                video_grid += f"""
                    <div class="video-item" style="--order: {i};">
                        <div class="video-wrapper">
                            <iframe 
                                src="{full_url}" 
                                frameborder="0" 
                                allow="encrypted-media" 
                                allowfullscreen
                            ></iframe>
                        </div>
                        <div class="video-info">
                            <h3>{video_title}</h3>
                            <div class="video-meta">
                                <span class="label">Date:</span> <span>{date_str}</span>
                                <span class="label">Time:</span> <span>{time_str}</span>
                                <span class="label">Uploaded:</span> <span>{hours_ago_str}</span>
                                <span class="label">User:</span> <span>{user}</span>
                            </div>
                            <button class="delete-btn" onclick="deleteVideo('{video_id}')">Delete</button>
                        </div>
                    </div>
                """
            else:
                logger.warning(f"Skipping video with missing token: {video}")

        # If no valid videos, add a placeholder
        if not video_grid:
            video_grid = "<p>No videos available to display.</p>"
            logger.warning("No valid videos found to display")

        # Insert video grid into template
        html_content = html_content.replace('<!-- VIDEO_GRID -->', video_grid)

        return web.Response(text=html_content, content_type="text/html")
    except Exception as e:
        logger.error(f"Error loading page: {str(e)}")
        return web.Response(text=f"Error loading page: {str(e)}", status=500)

async def delete_video(request):
    try:
        file_id = request.match_info.get('token')  # Rename to file_id for clarity, as it matches logs
        if not file_id:
            return web.Response(text="Video ID is required", status=400)

        # Check if the video exists in Supabase
        video_response = supabase.table("stream").select("*").eq("video", file_id).execute()
        if not video_response.data or len(video_response.data) == 0:
            logger.warning(f"Video not found in database for deletion: {file_id}")
            return web.Response(text="Video not found", status=404)

        # Delete from Supabase
        response = supabase.table("stream").delete().eq("video", file_id).execute()
        if not response.data:
            logger.warning(f"Video not found in database for deletion: {file_id}")
            return web.Response(text="Video not found", status=404)

        # Define paths
        downloads_dir = os.path.join(os.getcwd(), "downloads")
        originals_dir = os.path.join(os.getcwd(), "originals")
        hls_folder = os.path.join(downloads_dir, file_id)

        # Delete HLS folder if it exists
        if os.path.exists(hls_folder):
            try:
                shutil.rmtree(hls_folder)
                logger.info(f"Successfully deleted HLS folder: {hls_folder}")
            except Exception as file_error:
                logger.error(f"Failed to delete HLS folder {hls_folder}: {str(file_error)}")
        else:
            logger.warning(f"HLS folder not found for file_id: {file_id}")

        # Delete original file (try common extensions)
        possible_extensions = ['.mp4', '.mkv', '.avi', '.mov']
        original_file_path = None
        for ext in possible_extensions:
            candidate_path = os.path.join(originals_dir, f"{file_id}{ext}")
            if os.path.exists(candidate_path):
                original_file_path = candidate_path
                break

        if original_file_path:
            try:
                os.remove(original_file_path)
                logger.info(f"Successfully deleted original file: {original_file_path}")
            except Exception as file_error:
                logger.error(f"Failed to delete original file {original_file_path}: {str(file_error)}")
        else:
            logger.warning(f"Original file not found for file_id: {file_id} in {originals_dir}")

        logger.info(f"Successfully deleted video with file_id: {file_id} from database")
        return web.Response(text="Video deleted successfully", status=200)

    except Exception as e:
        logger.error(f"Error deleting video: {str(e)}")
        return web.Response(text=f"Error deleting video: {str(e)}", status=500)