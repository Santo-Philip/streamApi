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
                .vjs-control-bar {{
                    background: linear-gradient(to top, rgba(0,0,0,0.9), rgba(0,0,0,0.7));
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
                .subtitle-overlay {{
                    position: absolute;
                    bottom: 60px;
                    left: 10px;
                    right: 10px;
                    color: #fff;
                    background: rgba(0,0,0,0.7);
                    padding: 10px;
                    border-radius: 3px;
                    font-family: Arial, sans-serif;
                    font-size: 18px;
                    text-align: center;
                    z-index: 1000;
                    text-shadow: 1px 1px 2px #000;
                }}
                .settings-button {{
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    z-index: 1000;
                    cursor: pointer;
                    padding: 5px;
                    background: rgba(0,0,0,0.7);
                    border-radius: 3px;
                }}
                .settings-menu {{
                    display: none;
                    position: absolute;
                    top: 40px;
                    right: 10px;
                    background: rgba(0,0,0,0.9);
                    color: #fff;
                    padding: 10px;
                    border-radius: 5px;
                    z-index: 1001;
                    min-width: 200px;
                }}
                .settings-menu.show {{
                    display: block;
                }}
                .settings-item {{
                    padding: 5px 0;
                    cursor: pointer;
                }}
                .settings-item:hover {{
                    background: #ff416c;
                }}
                .settings-item select {{
                    width: 100%;
                    background: #333;
                    color: #fff;
                    border: none;
                    padding: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="video-container">
                <video id="video-player" class="video-js" controls preload="metadata">
                    <source src="{hls_path}" type="application/x-mpegURL">
                </video>
                <div class="overlay-filename">{filename}</div>
                <div class="subtitle-overlay" id="subtitle-overlay"></div>
                <div class="settings-button" onclick="toggleSettings()">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="#fff">
                        <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.43-.48-.43h-3.84c-.24 0-.43.19-.47.43l-.36 2.54c-.59.24-1.13.56-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.3-.06.62-.06.94s.02.64.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.43.48.43h3.84c.24 0 .44-.19.47-.43l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
                    </svg>
                </div>
                <div class="settings-menu" id="settings-menu">
                    <div class="settings-item">
                        <label>Audio Track:</label>
                        <select id="audio-tracks"></select>
                    </div>
                    <div class="settings-item">
                        <label>Subtitles:</label>
                        <select id="subtitle-tracks">
                            <option value="off">Off</option>
                        </select>
                    </div>
                    <div class="settings-item">
                        <label>Playback Speed:</label>
                        <select id="playback-speed">
                            <option value="0.5">0.5x</option>
                            <option value="0.75">0.75x</option>
                            <option value="1" selected>1x</option>
                            <option value="1.25">1.25x</option>
                            <option value="1.5">1.5x</option>
                            <option value="2">2x</option>
                        </select>
                    </div>
                    <div class="settings-item">
                        <label>Quality:</label>
                        <select id="quality-select">
                            <option value="auto" selected>Auto</option>
                        </select>
                    </div>
                </div>
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
                        player.play().catch(err => console.log('Autoplay failed:', err));
                    }}

                    // Audio Tracks
                    const audioTracks = player.audioTracks();
                    const audioSelect = document.getElementById('audio-tracks');
                    audioTracks.on('change', function() {{
                        const activeTrack = Array.from(audioTracks).find(t => t.enabled);
                        audioSelect.value = activeTrack ? activeTrack.id : '';
                    }});
                    for (let i = 0; i < audioTracks.length; i++) {{
                        const track = audioTracks[i];
                        const option = document.createElement('option');
                        option.value = track.id;
                        option.text = track.label || `Track ${i + 1}`;
                        if (track.enabled) option.selected = true;
                        audioSelect.appendChild(option);
                    }}
                    audioSelect.onchange = function() {{
                        for (let i = 0; i < audioTracks.length; i++) {{
                            audioTracks[i].enabled = audioTracks[i].id === this.value;
                        }}
                    }};

                    // Subtitles
                    const textTracks = player.textTracks();
                    const subtitleSelect = document.getElementById('subtitle-tracks');
                    const subtitleOverlay = document.getElementById('subtitle-overlay');
                    for (let i = 0; i < textTracks.length; i++) {{
                        const track = textTracks[i];
                        if (track.kind === 'subtitles' || track.kind === 'captions') {{
                            const option = document.createElement('option');
                            option.value = track.label;
                            option.text = track.label || `Subtitle ${i + 1}`;
                            subtitleSelect.appendChild(option);
                        }}
                    }}
                    subtitleSelect.onchange = function() {{
                        for (let i = 0; i < textTracks.length; i++) {{
                            textTracks[i].mode = (this.value === 'off' || textTracks[i].label !== this.value) ? 'disabled' : 'showing';
                        }}
                    }};
                    textTracks.on('change', function() {{
                        const activeTrack = Array.from(textTracks).find(t => t.mode === 'showing');
                        subtitleOverlay.textContent = activeTrack && activeTrack.activeCues && activeTrack.activeCues[0] ? activeTrack.activeCues[0].text : '';
                        subtitleSelect.value = activeTrack ? activeTrack.label : 'off';
                    }});

                    // Playback Speed
                    document.getElementById('playback-speed').onchange = function() {{
                        player.playbackRate(parseFloat(this.value));
                    }};

                    // Quality (basic implementation - may need adjustment based on HLS manifest)
                    const qualitySelect = document.getElementById('quality-select');
                    player.on('loadedmetadata', function() {{
                        const levels = player.qualityLevels?.();
                        if (levels) {{
                            levels.on('change', () => {{
                                qualitySelect.value = levels.selectedIndex === -1 ? 'auto' : levels[levels.selectedIndex].height + 'p';
                            }});
                            for (let i = 0; i < levels.length; i++) {{
                                const option = document.createElement('option');
                                option.value = levels[i].height + 'p';
                                option.text = levels[i].height + 'ps';
                                qualitySelect.appendChild(option);
                            }}
                        }}
                    }});
                    qualitySelect.onchange = function() {{
                        const levels = player.qualityLevels();
                        if (this.value === 'auto') {{
                            for (let i = 0; i < levels.length; i++) levels[i].enabled = true;
                        }} else {{
                            const height = parseInt(this.value);
                            for (let i = 0; i < levels.length; i++) {{
                                levels[i].enabled = levels[i].height === height;
                            }}
                        }}
                    }};
                }});

                function toggleSettings() {{
                    const menu = document.getElementById('settings-menu');
                    menu.classList.toggle('show');
                }}

                player.on('error', function() {{
                    player.errorDisplay.open();
                }});
            </script>
        </body>
        </html>
        """
        response = web.Response(text=html_content, content_type='text/html')
        response.headers['X-Frame-Options'] = 'ALLOWALL'
        return response
    except Exception as e:
        logger.error(f"Error serving video player: {str(e)}")
        return web.Response(text=f"Error serving video player: {str(e)}", status=500)