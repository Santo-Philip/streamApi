import os
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

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{video_title}</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link href="https://vjs.zencdn.net/8.10.0/video-js.css" rel="stylesheet" />
            <script src="https://vjs.zencdn.net/8.10.0/video.min.js"></script>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background: #000;
                    overflow: hidden;
                }}
                .video-container {{
                    position: relative;
                    width: 100%;
                    height: 100vh;
                }}
                .video-js {{
                    width: 100%;
                    height: 100%;
                }}
                .overlay-filename {{
                    position: absolute;
                    top: 10px;
                    left: 10px;
                    color: #fff;
                    background: rgba(0,0,0,0.7);
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-family: Arial, sans-serif;
                    z-index: 1000;
                }}
            </style>
        </head>
        <body>
            <div class="video-container">
                <video id="video-player" class="video-js" controls preload="metadata">
                    <source src="{hls_path}" type="application/x-mpegURL">
                </video>
                <div class="overlay-filename">{filename}</div>
            </div>
            <script>
                const player = videojs('video-player', {{
                    fluid: true,
                    responsive: true,
                    autoplay: {str(should_autoplay).lower()},
                    muted: {str(should_autoplay).lower()},
                    html5: {{
                        hls: {{
                            enableLowInitialPlaylist: true,
                            overrideNative: true
                        }}
                    }},
                    controlBar: {{
                        volumePanel: {{ inline: true }},
                        fullscreenToggle: true,
                        pictureInPictureToggle: true
                    }}
                }});

                player.ready(function() {{
                    if ({str(should_autoplay).lower()}) {{
                        player.play().catch(function(err) {{
                            console.log('Autoplay failed:', err);
                        }});
                    }}
                }});
            </script>
        </body>
        </html>
        """
        return web.Response(text=html_content, content_type="text/html")

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return web.Response(text="Internal server error", status=500)
