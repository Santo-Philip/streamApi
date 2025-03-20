import time
from aiohttp import web
import psutil
import asyncio
import os

async def get_server_stats():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()
    uptime = time.time() - psutil.boot_time()  # Seconds since boot
    return {
        'cpu': cpu,
        'ram': ram.percent,
        'ramUsed': ram.used / 1024 / 1024,  # MB
        'ramTotal': ram.total / 1024 / 1024,  # MB
        'disk': disk.percent,
        'diskUsed': disk.used / 1024 / 1024 / 1024,  # GB
        'diskTotal': disk.total / 1024 / 1024 / 1024,  # GB
        'bandwidth_sent': net.bytes_sent / 1024 / 1024,  # MB
        'bandwidth_recv': net.bytes_recv / 1024 / 1024,  # MB
        'uptime': uptime  # Seconds
    }

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    while not ws.closed:
        stats = await get_server_stats()
        await ws.send_json(stats)
        await asyncio.sleep(2)
    return ws

async def index_handler(request):
    file_path = os.path.join(os.path.dirname(__file__), 'server.html')
    with open(file_path, 'r') as f:
        return web.Response(text=f.read(), content_type='text/html')