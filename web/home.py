import os
import traceback
import uuid
from aiohttp import web
from typing import Optional, Dict, Any
import logging

from dotenv import load_dotenv

from database.spbase import supabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()
BASE_DIR = os.path.join(os.getcwd(), "downloads")
logo_url = os.getenv("LOGO", "https://example.com/default-logo.png")

if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)


async def hello(request):
    """Serve the basic HTML page"""
    try:
        file_path = os.path.join(os.path.dirname(__file__), "video.html")
        if not os.path.exists(file_path):
            return web.Response(text="Video HTML template not found", status=404)

        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return web.Response(text=html_content, content_type="text/html")
    except Exception as e:
        logger.error(f"Error loading page: {str(e)}")
        return web.Response(text=f"Error loading page: {str(e)}", status=500)


async def fetch_video(id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Fetch video details from Supabase stream table by token"""
    try:
        # For supabase-py v2.x.x with async support
        response = supabase.table("stream") \
            .select("*") \
            .eq("token", str(id)) \
            .limit(1)

        # Execute the query synchronously since execute() might not be awaitable
        result = response.execute()

        if result.data and len(result.data) > 0:
            return result.data[0]  # Return first item directly
        return None
    except Exception as e:
        logger.error(f"Error fetching video with token {id}: {str(e)}")
        raise


async def fetch_video_details(token: str) -> Optional[Dict[str, Any]]:
    """Fetch video details from Supabase using the token"""
    try:
        if not token:
            logger.warning("No token provided")
            return None

        try:
            uuid_token = uuid.UUID(token)
        except ValueError:
            logger.warning(f"Invalid UUID format: {token}")
            return None

        video_data = await fetch_video(uuid_token)
        return video_data
    except Exception as e:
        logger.error(f"Error in fetch_video_details: {str(e)}")
        return None


async def serve_hls(request):
    """Serve HLS .m3u8 and .ts files from the downloads folder"""
    try:
        file_name = request.match_info.get('file', 'output.m3u8')
        file_path = os.path.join(BASE_DIR, file_name)

        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_name}")
            return web.Response(text=f"File not found: {file_name}", status=404)

        content_type = ('application/vnd.apple.mpegurl' if file_name.endswith('.m3u8')
                        else 'video/mp2t')
        return web.FileResponse(file_path, headers={'Content-Type': content_type})
    except Exception as e:
        logger.error(f"Error serving HLS file: {str(e)}")
        return web.Response(text=f"Error serving HLS file: {str(e)}", status=500)


async def serve_video_player(request):
    try:
        token = request.match_info.get('token')
        if not token:
            logger.warning("Token is required")
            return web.Response(text="Token is required", status=400)

        video_details = await fetch_video_details(token)
        if not video_details:
            logger.warning(f"Video not found for token: {token}")
            return web.Response(text="Invalid token or video not found", status=404)

        video_id = video_details.get("video")
        if not video_id:
            logger.warning(f"Video ID not found in details for token: {token}")
            return web.Response(text="Video ID not found in details", status=404)

        should_autoplay = request.query.get('play', '').lower() == 'true'
        hls_path = f"/hls/{video_id}/master.m3u8"
        video_title = video_details.get('title', 'Video Player')
        filename = video_details.get('filename', video_id)

        # Log the substituted values for debugging
        logger.info(f"Video ID: {video_id}")
        logger.info(f"HLS Path: {hls_path}")
        logger.info(f"Video Title: {video_title}")
        logger.info(f"Filename: {filename}")
        logger.info(f"Should Autoplay: {should_autoplay}")

        html_file_path = os.path.join(os.path.dirname(__file__), 'player.html')

        if not os.path.exists(html_file_path):
            raise FileNotFoundError(f"HTML file not found at: {html_file_path}")

        with open(html_file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()

        # Escape all curly braces
        html_content = html_content.replace("{", "{{").replace("}", "}}")

        # Replace specific placeholders
        html_content = html_content.replace("{{video_title}}", video_title)
        html_content = html_content.replace("{{hls_path}}", hls_path)
        html_content = html_content.replace("{{filename}}", filename)
        html_content = html_content.replace("{{should_autoplay}}", str(should_autoplay).lower())

        response = web.Response(text=html_content, content_type='text/html')
        response.headers['X-Frame-Options'] = 'ALLOWALL'
        return response

    except FileNotFoundError as e:
        logger.error(f"File error: {str(e)}")
        return web.Response(text="Server configuration error: Video player template not found", status=500)
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error serving video player: {str(e)}\nFull traceback: {error_details}")
        return web.Response(text=f"Error serving video player: {str(e)}\nDetails: {error_details}", status=500)