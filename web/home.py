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
        with open('player.html', 'r', encoding='utf-8') as file:
            html_content = file.read()

        escaped_html = escape_braces_in_html(html_content)

        with open('player.html', 'w', encoding='utf-8') as file:
            file.write(escaped_html)

        token = request.match_info.get('token')
        if not token:
            logger.warning("Token is required")
            return web.Response(text="Token is required", status=400)

        # Fetch video details based on the token
        video_details = await fetch_video_details(token)
        if not video_details:
            logger.warning(f"Video not found for token: {token}")
            return web.Response(text="Invalid token or video not found", status=404)

        # Extract video ID and other details
        video_id = video_details.get("video")
        if not video_id:
            logger.warning(f"Video ID not found in details for token: {token}")
            return web.Response(text="Video ID not found in details", status=404)

        # Determine autoplay behavior
        should_autoplay = request.query.get('play', '').strip().lower() in ['true', '1', 'yes']

        # HLS path for video streaming
        hls_path = f"/hls/{video_id}/master.m3u8"

        # Fallback values for title and filename
        video_title = video_details.get('title', 'Video Player')
        filename = video_details.get('filename', video_id)

        # Path to the HTML file
        html_file_path = os.path.join(os.path.dirname(__file__), 'player.html')

        # Check if the file exists
        if not os.path.exists(html_file_path):
            logger.error(f"HTML file not found at: {html_file_path}")
            return web.Response(text="Server error: HTML template not found", status=500)

        # Read the HTML template
        with open(html_file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()

        # Log raw HTML length for debugging
        logger.debug(f"Raw HTML content length: {len(html_content)}")

        # Safely format placeholders in the HTML
        try:
            html_content = html_content.format(
                video_title=safe_str(video_title),
                hls_path=safe_str(hls_path),
                filename=safe_str(filename),
                should_autoplay=str(should_autoplay).lower()
            )
        except KeyError as ke:
            logger.error(f"Missing placeholder in HTML: {ke}")
            return web.Response(text=f"Template error: Missing placeholder {ke}", status=500)
        except Exception as e:
            logger.error(f"Error formatting HTML template: {e}")
            return web.Response(text=f"Error formatting template: {e}", status=500)

        # Log the formatted HTML length for debugging
        logger.debug(f"Formatted HTML content length: {len(html_content)}")

        # Create a response with the formatted HTML content
        response = web.Response(text=html_content, content_type='text/html')
        response.headers['X-Frame-Options'] = 'ALLOWALL'
        return response

    except FileNotFoundError as e:
        # Log file-specific errors
        logger.error(f"File error: {str(e)}")
        return web.Response(text="Server error: Video player template not found", status=500)

    except Exception as e:
        # Log full traceback for debugging unexpected errors
        error_details = traceback.format_exc()
        logger.error(f"Error serving video player: {str(e)}\nFull traceback: {error_details}")
        return web.Response(text=f"Unexpected error: {str(e)}\nDetails: {error_details}", status=500)


def safe_str(value):
    """
    Safely converts a value to a string, escaping special characters to avoid HTML template issues.
    """
    return str(value).replace("{", "{{").replace("}", "}}")

def escape_braces_in_html(html_content):
    """
    Escapes all standalone { and } in the HTML content to {{ and }} to avoid formatting issues.
    """
    return html_content.replace("{", "{{").replace("}", "}}")