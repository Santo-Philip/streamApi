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
        autoplay_value = str(should_autoplay).lower()
        hls_path = f"/hls/{video_id}/master.m3u8"
        video_title = video_details.get('title', 'Video Player')
        filename = video_details.get('filename', video_id)
        logo_url = "https://example.com/logo.png"  # Replace with your logo URL or remove

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
                .vjs-menu-button-popup .vjs-menu .vjs-menu-content {{
                    background-color: rgba(0, 0, 0, 0.8);
                    color: #fff;
                }}
                .vjs-menu-button-popup .vjs-menu .vjs-menu-item:hover {{
                    background-color: #ff416c;
                }}
                .logo {{
                    position: absolute;
                    top: 1vw;
                    right: 1vw;
                    width: 5vw;
                    max-width: 50px;
                    min-width: 20px;
                    opacity: 0.5;
                    pointer-events: none;
                    z-index: 1000;
                    transition: opacity 0.3s ease;
                }}
                .logo:hover {{
                    opacity: 0.8;
                }}
                @media (max-width: 600px) {{
                    .logo {{
                        top: 0.5vw;
                        right: 0.5vw;
                        width: 6vw;
                    }}
                }}
                .vjs-error-display {{
                    color: #ff4444;
                    text-align: center;
                }}
                .video-title {{
                    position: absolute;
                    top: 10px;
                    left: 10px;
                    color: #fff;
                    font-family: Arial, sans-serif;
                    font-size: 16px;
                    padding: 5px 10px;
                    background: linear-gradient(to top, rgba(0,0,0,0.9), rgba(0,0,0,0.7));
                    border-radius: 3px;
                    opacity: 0;
                    z-index: 1000;
                    transition: opacity 0.3s ease;
                }}
                .vjs-control-bar:not(.vjs-hidden) ~ .video-title {{
                    opacity: 1;
                }}
                .settings-button {{
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    color: #fff;
                    background: rgba(0,0,0,0.7);
                    padding: 5px;
                    border-radius: 3px;
                    cursor: pointer;
                    z-index: 1000;
                    opacity: 0;
                    transition: opacity 0.3s ease;
                }}
                .vjs-control-bar:not(.vjs-hidden) ~ .settings-button {{
                    opacity: 1;
                }}
                .settings-overlay {{
                    display: none;
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: rgba(0, 0, 0, 0.9);
                    z-index: 2000;
                    color: #fff;
                    font-family: Arial, sans-serif;
                    overflow-y: auto;
                }}
                .settings-overlay.show {{
                    display: block;
                }}
                .settings-content {{
                    padding: 20px;
                    max-width: 400px;
                    margin: 50px auto;
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 5px;
                }}
                .settings-item {{
                    margin-bottom: 15px;
                }}
                .settings-item label {{
                    display: block;
                    margin-bottom: 5px;
                }}
                .settings-item select {{
                    width: 100%;
                    padding: 5px;
                    background: #333;
                    color: #fff;
                    border: none;
                    border-radius: 3px;
                }}
                .close-button {{
                    position: absolute;
                    top: 10px;
                    right: 10px;
                    color: #fff;
                    font-size: 24px;
                    cursor: pointer;
                }}
                .overlay-filename {{
                    position: absolute;
                    top: 40px;
                    left: 10px;
                    color: #fff;
                    background: rgba(0,0,0,0.7);
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-family: Arial, sans-serif;
                    z-index: 1000;
                }}
                .seek-info {{
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    color: #fff;
                    font-family: Arial, sans-serif;
                    font-size: 24px;
                    padding: 10px 20px;
                    background: rgba(0, 0, 0, 0.8);
                    border-radius: 5px;
                    opacity: 0;
                    z-index: 1000;
                    pointer-events: none;
                    transition: opacity 0.3s ease, transform 0.3s ease;
                }}
                .seek-info.show {{
                    opacity: 1;
                    transform: translate(-50%, -60%);
                }}
            </style>
        </head>
        <body>
            <div class="video-container">
                <video id="video-player" class="video-js" controls preload="metadata">
                    <source src="{hls_path}" type="application/x-mpegURL">
                    Your browser does not support the video tag.
                </video>
                <img src="{logo_url}" class="logo" alt="Logo" onerror="this.style.display='none'">
                <div class="video-title">{video_title}</div>
                <div class="overlay-filename">{filename}</div>
                <div class="settings-button" onclick="toggleSettings()">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="#fff">
                        <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.43-.48-.43h-3.84c-.24 0-.43.19-.47.43l-.36 2.54c-.59.24-1.13.56-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.3-.06.62-.06.94s.02.64.06.94l-2.03 1.58c-.18.14-.23.41-.12-.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.43.48.43h3.84c.24 0 .44-.19.47-.43l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
                    </svg>
                </div>
                <div class="seek-info" id="seek-info"></div>
                <div class="settings-overlay" id="settings-overlay">
                    <span class="close-button" onclick="toggleSettings()">×</span>
                    <div class="settings-content">
                        <h2>Settings</h2>
                        <div class="settings-item">
                            <label>Audio Track</label>
                            <select id="audio-tracks"></select>
                        </div>
                        <div class="settings-item">
                            <label>Subtitles/Captions</label>
                            <select id="subtitle-tracks">
                                <option value="off">Off</option>
                            </select>
                        </div>
                    </div>
                </div>
            </div>
            <script>
                const player = videojs('video-player', {{
                    fluid: true,
                    responsive: true,
                    autoplay: {autoplay_value},
                    muted: {autoplay_value},
                    html5: {{
                        hls: {{
                            enableLowInitialPlaylist: true
                        }}
                    }},
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

                player.on('error', function() {{
                    player.errorDisplay.open();
                }});

                player.ready(function() {{
                    if ({autoplay_value}) {{
                        player.play().catch(function(err) {{
                            console.log('Autoplay failed:', err);
                        }});
                    }}

                    // Audio Tracks
                    const audioTracks = player.audioTracks();
                    const audioSelect = document.getElementById('audio-tracks');
                    if (audioTracks && audioTracks.length > 0) {{
                        for (let i = 0; i < audioTracks.length; i++) {{
                            const track = audioTracks[i];
                            const option = document.createElement('option');
                            option.value = track.id;
                            if (track.enabled) option.selected = true;
                            audioSelect.appendChild(option);
                        }}
                        audioSelect.onchange = function() {{
                            const tracks = player.audioTracks();
                            for (let i = 0; i < tracks.length; i++) {{
                                tracks[i].enabled = tracks[i].id === this.value;
                            }}
                        }};
                        audioTracks.on('change', function() {{
                            const tracks = player.audioTracks();
                            const activeTrack = Array.from(tracks).find(t => t.enabled);
                            audioSelect.value = activeTrack ? activeTrack.id : '';
                            console.log('Switched to audio track:', activeTrack ? activeTrack.label : 'None');
                        }});
                    }}

                    // Subtitles/Captions
                    const textTracks = player.textTracks();
                    const subtitleSelect = document.getElementById('subtitle-tracks');
                    if (textTracks && textTracks.length > 0) {{
                        for (let i = 0; i < textTracks.length; i++) {{
                            const track = textTracks[i];
                            if (track.kind === 'subtitles' || track.kind === 'captions') {{
                                const option = document.createElement('option');
                                option.value = track.label;
                                subtitleSelect.appendChild(option);
                            }}
                        }}
                        subtitleSelect.onchange = function() {{
                            const tracks = player.textTracks();
                            for (let i = 0; i < tracks.length; i++) {{
                                tracks[i].mode = (this.value === 'off' || tracks[i].label !== this.value) ? 'disabled' : 'showing';
                            }}
                        }};
                        textTracks.on('change', function() {{
                            const tracks = player.textTracks();
                            const activeTrack = Array.from(tracks).find(t => t.mode === 'showing');
                            subtitleSelect.value = activeTrack ? activeTrack.label : 'off';
                            console.log('Switched to subtitle track:', activeTrack ? activeTrack.label : 'None');
                        }});
                    }}

                    player.on('loadedmetadata', function() {{
                        console.log('Audio tracks:', audioTracks ? audioTracks.length : 0);
                        console.log('Text tracks:', textTracks ? textTracks.length : 0);
                    }});
                }});

                let lastTap = 0;
                player.on('touchend', function(e) {{
                    const now = Date.now();
                    const timeSinceLastTap = now - lastTap;
                    const videoRect = player.el().getBoundingClientRect();
                    const tapX = e.changedTouches[0].clientX - videoRect.left;

                    if (timeSinceLastTap < 300 && timeSinceLastTap > 0) {{
                        const seekTime = tapX < videoRect.width / 2 ? -10 : 10;
                        player.currentTime(player.currentTime() + seekTime);
                        showSeekInfo(seekTime);
                    }}
                    lastTap = now;
                }});

                let isDragging = false;
                let startX, startTime;
                player.on('touchstart', function(e) {{
                    isDragging = true;
                    startX = e.touches[0].clientX;
                    startTime = player.currentTime();
                }});

                player.on('touchmove', function(e) {{
                    if (!isDragging) return;
                    const videoRect = player.el().getBoundingClientRect();
                    const currentX = e.touches[0].clientX;
                    const deltaX = currentX - startX;
                    const duration = player.duration() || 0;
                    const seekRange = duration * (deltaX / videoRect.width);
                    const newTime = Math.max(0, Math.min(duration, startTime + seekRange));
                    player.currentTime(newTime);
                }});

                player.on('touchend', function() {{
                    if (isDragging) {{
                        const seekTime = player.currentTime() - startTime;
                        if (Math.abs(seekTime) > 1) {{
                            showSeekInfo(seekTime);
                        }}
                    }}
                    isDragging = false;
                }});

                function showSeekInfo(seekTime) {{
                    const seekInfo = document.getElementById('seek-info');
                    seekInfo.textContent = (seekTime > 0 ? '+' : '') + Math.round(seekTime) + 's';
                    seekInfo.classList.add('show');
                    setTimeout(() => {{
                        seekInfo.classList.remove('show');
                    }}, 1000);
                }}

                function toggleSettings() {{
                    const overlay = document.getElementById('settings-overlay');
                    overlay.classList.toggle('show');
                }}

                player.on('loadedmetadata', function() {{
                    document.querySelector('.logo').style.zIndex = '1000';
                    document.querySelector('.video-title').style.zIndex = '1000';
                    document.querySelector('.settings-button').style.zIndex = '1000';
                }});
            </script>
        </body>
        </html>
        """
        response = web.Response(text=html_content, content_type='text/html')
        response.headers['X-Frame-Options'] = 'ALLOWALL'
        return response
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"Error serving video player: {str(e)}\nFull traceback: {error_details}")
        return web.Response(text=f"Error serving video player: {str(e)}", status=500)