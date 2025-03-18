from aiohttp import web
from web.home import hello, serve_hls, serve_video_player
import logging

from web.index import video_index
from web.protected_page import auth_middleware

logger = logging.getLogger(__name__)
async def start_web_server():
    app = web.Application(middlewares=[auth_middleware])
    app.router.add_get('/', hello)
    app.router.add_get('/hls/{file:.+}', serve_hls)
    app.router.add_get('/video/{token}', serve_video_player)
    app.router.add_get('/videos', video_index)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("AioHTTP server started on port 8080")