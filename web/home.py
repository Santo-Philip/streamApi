import os
import uuid
from aiohttp import web
from typing import Optional, Dict, Any
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta
import secrets

from database.spbase import supabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# Configuration
BASE_DIR = os.path.join(os.getcwd(), "downloads")
LOGO_URL = os.getenv("LOGO", "https://example.com/default-logo.png")
ALLOWED_ORIGINS = {os.getenv("ALLOWED_ORIGIN", "https://media.mehub.in")}
TOKEN_EXPIRY = timedelta(minutes=15)
CDN_BASE_URL = os.getenv("CDN_BASE_URL", "")  # Add your CDN URL in .env

# Token storage (consider Redis in production)
active_tokens: Dict[str, Dict[str, Any]] = {}

os.makedirs(BASE_DIR, exist_ok=True)


async def generate_secure_token(video_id: str) -> str:
    """Generate a secure, time-limited token for video access"""
    token = secrets.token_urlsafe(32)
    active_tokens[token] = {
        'video_id': video_id,
        'expiry': datetime.now() + TOKEN_EXPIRY,
        'used': False
    }
    return token


async def validate_token(token: str) -> Optional[str]:
    """Validate token and return video_id if valid"""
    if token not in active_tokens:
        return None

    token_info = active_tokens[token]
    if token_info['used'] or datetime.now() > token_info['expiry']:
        del active_tokens[token]
        return None

    token_info['used'] = True  # Mark as used for one-time access
    return token_info['video_id']


async def fetch_video_details(token: str) -> Optional[Dict[str, Any]]:
    """Fetch video details from Supabase with security checks"""
    try:
        if not token:
            return None

        uuid_token = uuid.UUID(token)  # Will raise ValueError if invalid
        response = await supabase.table("stream") \
            .select("video, title") \
            .eq("token", str(uuid_token)) \
            .limit(1) \
            .execute()

        return response.data[0] if response.data else None
    except (ValueError, Exception) as e:
        logger.error(f"Error fetching video details for token {token}: {str(e)}")
        return None


async def serve_hls(request):
    """Securely serve HLS files with CDN support"""
    try:
        # Origin check
        origin = request.headers.get('Origin')
        if origin not in ALLOWED_ORIGINS:
            return web.Response(text="Unauthorized origin", status=403)

        token = request.query.get('token')
        file_name = request.match_info.get('file', 'master.m3u8')

        if not token or not await validate_token(token):
            return web.Response(text="Invalid or expired token", status=401)

        file_path = os.path.join(BASE_DIR, file_name)
        if not file_path.startswith(BASE_DIR) or not file_name.endswith(('.m3u8', '.ts')):
            return web.Response(text="Invalid file access", status=403)

        if not os.path.exists(file_path):
            return web.Response(text="File not found", status=404)

        content_type = 'application/vnd.apple.mpegurl' if file_name.endswith('.m3u8') else 'video/mp2t'
        headers = {
            'Content-Type': content_type,
            'Cache-Control': 'no-store, no-cache, must-revalidate',
            'X-Content-Type-Options': 'nosniff'
        }
        return web.FileResponse(file_path, headers=headers)
    except Exception as e:
        logger.error(f"Error serving HLS: {str(e)}")
        return web.Response(text="Server error", status=500)


async def serve_video_player(request):
    """Serve secure video player with CDN optimization"""
    try:
        token = request.match_info.get('token')
        if not token:
            return web.Response(text="Token required", status=400)

        video_details = await fetch_video_details(token)
        if not video_details:
            return web.Response(text="Invalid token or video not found", status=404)

        video_id = video_details['video']
        video_title = video_details.get('title', 'Video Player')
        should_autoplay = request.query.get('play', 'false').lower() == 'true'

        # Use CDN if configured, otherwise local path
        hls_path = f"{CDN_BASE_URL}/hls/{video_id}/master.m3u8" if CDN_BASE_URL else f"/hls/{video_id}/master.m3u8?token={token}"

        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="ie=edge">
    <title>{video_title}</title>
    <link href="https://vjs.zencdn.net/8.10.0/video-js.css" rel="stylesheet" integrity="sha256-..." crossorigin="anonymous">
    <script src="https://vjs.zencdn.net/8.10.0/video.min.js" integrity="sha256-..." crossorigin="anonymous"></script>
    <style>
        body {{ margin: 0; padding: 0; background: #000; overflow: hidden; }}
        .video-js {{ width: 100vw; height: 100vh; }}
        .vjs-control-bar {{ background: rgba(0,0,0,0.7); height: 3em; }}
        .vjs-progress-holder {{ height: 6px; background: rgba(255,255,255,0.2); border-radius: 3px; }}
        .vjs-progress-holder:hover {{ height: 8px; }}
        .vjs-play-progress {{ background: #ff416c; }}
        .vjs-play-progress:before {{ 
            content: ''; position: absolute; right: -4px; top: 50%; 
            transform: translateY(-50%); width: 8px; height: 8px; 
            background: #fff; border-radius: 50%; 
        }}
        .logo {{ position: absolute; top: 10px; right: 10px; width: 40px; opacity: 0.7; z-index: 100; }}
        .video-title {{ 
            position: absolute; top: 10px; left: 10px; color: #fff; 
            padding: 5px 10px; background: rgba(0,0,0,0.7); border-radius: 3px; 
            font-family: Arial, sans-serif; z-index: 100; 
        }}
    </style>
</head>
<body>
    <video id="player" class="video-js" controls preload="metadata" 
           data-setup='{{"fluid": true, "autoplay": {str(should_autoplay).lower()}, "muted": {str(should_autoplay).lower()}}}'>
        <source src="{hls_path}" type="application/x-mpegURL">
    </video>
    <img src="{LOGO_URL}" class="logo" alt="Logo" onerror="this.style.display='none'">
    <div class="video-title">{video_title}</div>
    <script>
        const player = videojs('player', {{
            html5: {{ hls: {{ enableLowInitialPlaylist: true }} }},
            errorDisplay: true
        }});

        player.on('error', () => player.errorDisplay.open());

        player.ready(() => {{
            if ({str(should_autoplay).lower()}) {{
                player.play().catch(err => console.log('Autoplay failed:', err));
            }}
        }});
    </script>
</body>
</html>
"""
        response = web.Response(text=html_content, content_type='text/html')
        response.headers.update({
            'X-Frame-Options': 'DENY',  # Changed from ALLOWALL for security
            'Content-Security-Policy': "default-src 'self' https://vjs.zencdn.net; img-src 'self' data: https:;",
            'Cache-Control': 'no-store, no-cache, must-revalidate'
        })
        return response
    except Exception as e:
        logger.error(f"Error serving video player: {str(e)}")
        return web.Response(text="Server error", status=500)