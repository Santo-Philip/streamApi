from aiohttp import web
from web.home import  serve_hls, serve_video_player
import logging

from web.index import video_index, delete_video
from web.protected_page import auth_middleware
from web.server import websocket_handler, index_handler

logger = logging.getLogger(__name__)
async def start_web_server():
    app = web.Application(middlewares=[auth_middleware])
    app.router.add_get('/hls/{file:.+}', serve_hls)
    app.router.add_get('/video/{token}', serve_video_player)
    app.router.add_get('/videos', video_index)
    app.router.add_delete('/videos/{token}', delete_video)
    app.router.add_get('/server-stats', websocket_handler)
    app.router.add_get('/server', index_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    logger.info("AioHTTP server started on port 8080")