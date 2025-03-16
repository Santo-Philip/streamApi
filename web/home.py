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
logo_url = os.getenv("LOGO_URL", "https://example.com/default-logo.png")

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
    """Serve the video player page with HLS stream for embedding"""
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

        hls_path = f"/hls/{video_id}/output.m3u8"
        video_title = video_details.get('title', 'Video Player')

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
                    height: 100vh;
                    width: 100vw;
                }}
                .video-container {{
                    position: relative;
                    width: 100%;
                    height: 100%;
                }}
                .video-js {{ 
                    width: 100%; 
                    height: 100%;
                    border-radius: 0;
                }}
                .vjs-control-bar {{
                    background: linear-gradient(to top, rgba(0,0,0,0.9), rgba(0,0,0,0.7));
                    height: 3.5em;
                    padding: 0 10px;
                }}
                .vjs-progress-control {{
                    flex: 1;
                    margin: 0 10px;
                }}
                .vjs-progress-holder {{
                    height: 6px !important;
                    background: rgba(255, 255, 255, 0.2) !important;
                    border-radius: 3px;
                    overflow: hidden;
                    position: relative;
                    transition: all 0.2s ease;
                }}
                .vjs-progress-holder:hover {{
                    height: 8px !important;
                }}
                .vjs-load-progress {{
                    background: rgba(255, 255, 255, 0.4) !important;
                }}
                .vjs-play-progress {{
                    background: linear-gradient(90deg, #ff416c, #ff4b2b) !important;
                    border-radius: 3px;
                    position: relative;
                }}
                .vjs-play-progress:before {{
                    content: '';
                    position: absolute;
                    right: -6px;
                    top: 50%;
                    transform: translateY(-50%);
                    width: 12px;
                    height: 12px;
                    background: #fff;
                    border-radius: 50%;
                    box-shadow: 0 0 4px rgba(0,0,0,0.5);
                    transition: all 0.2s ease;
                }}
                .vjs-progress-holder:hover .vjs-play-progress:before {{
                    width: 14px;
                    height: 14px;
                }}
                .vjs-volume-panel .vjs-volume-bar {{
                    background: #fff;
                }}
                .vjs-button > .vjs-icon-placeholder:before {{
                    color: #fff;
                }}
                .logo {{
                    position: absolute;
                    top: 5px;
                    right: 5px;
                    width: 50px;
                    opacity: 0.5;
                    pointer-events: none;
                    z-index: 1000;
                }}
                .vjs-error-display {{
                    color: #ff4444;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="video-container">
                <video id="video-player" class="video-js" controls preload="auto" autoplay muted>
                    <source src="{hls_path}" type="application/x-mpegURL">
                    Your browser does not support the video tag.
                </video>
                <img src="{logo_url}" class="logo" alt="Logo" onerror="this.style.display='none'">
            </div>
            <script>
                const player = videojs('video-player', {{
                    fluid: true,
                    responsive: true,
                    controlBar: {{
                        volumePanel: {{ inline: true }},
                        fullscreenToggle: true,
                        pictureInPictureToggle: true,
                        currentTimeDisplay: true,
                        timeDivider: true,
                        durationDisplay: true,
                        remainingTimeDisplay: false,
                        progressControl: {{
                            seekBar: true
                        }}
                    }}
                }});

                player.on('error', () => {{
                    player.errorDisplay.open();
                }});

                player.ready(() => {{
                    player.play().catch(err => console.log('Autoplay failed:', err));
                }});

                // Double-tap to seek
                let lastTap = 0;
                player.on('touchend', (e) => {{
                    const now = Date.now();
                    const timeSinceLastTap = now - lastTap;
                    const videoRect = player.el().getBoundingClientRect();
                    const tapX = e.changedTouches[0].clientX - videoRect.left;

                    if (timeSinceLastTap < 300 && timeSinceLastTap > 0) {{
                        const seekTime = tapX < videoRect.width / 2 ? -10 : 10;
                        player.currentTime(player.currentTime() + seekTime);
                    }}
                    lastTap = now;
                }});

                // Drag to seek on video
                let isDragging = false;
                let startX, startTime;
                player.on('touchstart', (e) => {{
                    isDragging = true;
                    startX = e.touches[0].clientX;
                    startTime = player.currentTime();
                }});

                player.on('touchmove', (e) => {{
                    if (!isDragging) return;
                    const videoRect = player.el().getBoundingClientRect();
                    const currentX = e.touches[0].clientX;
                    const deltaX = currentX - startX;
                    const duration = player.duration() || 0;
                    const seekRange = duration * (deltaX / videoRect.width);
                    player.currentTime(Math.max(0, Math.min(duration, startTime + seekRange)));
                }});

                player.on('touchend', () => {{
                    isDragging = false;
                }});

                // Ensure logo stays above controls
                player.on('loadedmetadata', () => {{
                    document.querySelector('.logo').style.zIndex = '1000';
                }});
            </script>
        </body>
        </html>
        """
        response = web.Response(text=html_content, content_type='text/html')
        response.headers['X-Frame-Options'] = 'ALLOWALL'  # Allow embedding in iframes
        return response
    except Exception as e:
        logger.error(f"Error serving video player: {str(e)}")
        return web.Response(text=f"Error serving video player: {str(e)}", status=500)