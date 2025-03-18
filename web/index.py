import os
from aiohttp import web
from database.spbase import supabase

from web.home import logger


async def video_index(request):
    try:
        # Fetch videos from Supabase
        response = supabase.table("stream").select("*").execute()
        videos = response.data if hasattr(response, 'data') else []

        # Log video data for debugging
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

        # Generate video grid with iframes
        video_grid = ""
        for video in videos:
            video_url = video.get('token', '')
            video_title = video.get('title', 'Untitled')
            if video_url:
                full_url = f"https://media.mehub.in/video/{video_url}"
                video_grid += f"""
                    <div class="video-item">
                        <iframe 
                            src="{full_url}" 
                            frameborder="0" 
                            allow="encrypted-media" 
                            allowfullscreen
                        ></iframe>
                        <h3>{video_title}</h3>
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