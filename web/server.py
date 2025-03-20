from aiohttp import web
import psutil
import asyncio
import os
import json
import time
import platform

async def get_server_stats():
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()
    cpu_speed = cpu_freq.current if cpu_freq else 0  # MHz
    cpu_model = platform.processor() or "Unknown"

    # RAM
    ram = psutil.virtual_memory()
    ram_used = ram.used / 1024 / 1024 / 1024  # GB
    ram_total = ram.total / 1024 / 1024 / 1024  # GB

    # Disk
    disk = psutil.disk_usage('/')
    disk_used = disk.used / 1024 / 1024 / 1024  # GB
    disk_total = disk.total / 1024 / 1024 / 1024  # GB

    # Bandwidth
    net = psutil.net_io_counters()
    bandwidth_sent_total = net.bytes_sent / 1024 / 1024  # MB
    bandwidth_recv_total = net.bytes_recv / 1024 / 1024  # MB
    # Today's bandwidth (reset daily, requires tracking; here we show total for simplicity)
    # For daily, you'd need persistent storage; this is cumulative for now

    # Uptime
    uptime_seconds = time.time() - psutil.boot_time()

    return {
        'cpu': cpu_percent,
        'cpu_count': cpu_count,
        'cpu_speed': cpu_speed / 1000 if cpu_speed else 0,  # GHz
        'cpu_model': cpu_model,
        'ram': ram.percent,
        'ram_used': ram_used,
        'ram_total': ram_total,
        'disk': disk.percent,
        'disk_used': disk_used,
        'disk_total': disk_total,
        'bandwidth_sent_total': bandwidth_sent_total,
        'bandwidth_recv_total': bandwidth_recv_total,
        'uptime': uptime_seconds
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
