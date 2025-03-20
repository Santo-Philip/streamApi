from aiohttp import web
import psutil
import asyncio
import os
import json
import time
import platform
from datetime import datetime


async def get_server_stats():
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq() or psutil._common.scpufreq(0, 0, 0)
    cpu_speed = cpu_freq.current / 1000 if cpu_freq.current else 0  # GHz
    cpu_temp = psutil.sensors_temperatures().get('coretemp', [None])[0].current if psutil.sensors_temperatures().get(
        'coretemp') else 0
    load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)

    # RAM
    ram = psutil.virtual_memory()
    ram_used_mb = ram.used / 1024 / 1024
    ram_total_mb = ram.total / 1024 / 1024
    ram_used_gb = ram.used / 1024 / 1024 / 1024
    ram_total_gb = ram.total / 1024 / 1024 / 1024
    ram_used_tb = ram.used / 1024 / 1024 / 1024 / 1024
    ram_total_tb = ram.total / 1024 / 1024 / 1024 / 1024

    # Disk
    disk = psutil.disk_usage('/')
    disk_used_mb = disk.used / 1024 / 1024
    disk_total_mb = disk.total / 1024 / 1024
    disk_used_gb = disk.used / 1024 / 1024 / 1024
    disk_total_gb = disk.total / 1024 / 1024 / 1024
    disk_used_tb = disk.used / 1024 / 1024 / 1024 / 1024
    disk_total_tb = disk.total / 1024 / 1024 / 1024 / 1024

    # Bandwidth
    net = psutil.net_io_counters()
    bandwidth_sent_total_mb = net.bytes_sent / 1024 / 1024
    bandwidth_recv_total_mb = net.bytes_recv / 1024 / 1024
    bandwidth_sent_total_gb = net.bytes_sent / 1024 / 1024 / 1024
    bandwidth_recv_total_gb = net.bytes_recv / 1024 / 1024 / 1024
    bandwidth_sent_total_tb = net.bytes_sent / 1024 / 1024 / 1024 / 1024
    bandwidth_recv_total_tb = net.bytes_recv / 1024 / 1024 / 1024 / 1024

    # Network Speed (Fixed)
    net_stats = psutil.net_if_stats()
    net_speed = 0
    for interface, stats in net_stats.items():
        if stats.isup and stats.speed > 0:  # Use first active interface with valid speed
            net_speed = stats.speed / 1000  # Convert Mbps to Gbps
            break

    # Other Stats
    connections = len(psutil.net_connections())
    uptime_seconds = time.time() - psutil.boot_time()
    server_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    timezone = time.tzname[0] if time.tzname else "Unknown"
    boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')

    return {
        'cpu': cpu_percent, 'cpu_count': cpu_count, 'cpu_speed': cpu_speed, 'cpu_temp': cpu_temp,
        'load_avg': load_avg[0], 'ram': ram.percent, 'ram_used_mb': ram_used_mb, 'ram_total_mb': ram_total_mb,
        'ram_used_gb': ram_used_gb, 'ram_total_gb': ram_total_gb, 'ram_used_tb': ram_used_tb,
        'ram_total_tb': ram_total_tb,
        'disk': disk.percent, 'disk_used_mb': disk_used_mb, 'disk_total_mb': disk_total_mb,
        'disk_used_gb': disk_used_gb, 'disk_total_gb': disk_total_gb, 'disk_used_tb': disk_used_tb,
        'disk_total_tb': disk_total_tb,
        'bandwidth_sent_total_mb': bandwidth_sent_total_mb, 'bandwidth_recv_total_mb': bandwidth_recv_total_mb,
        'bandwidth_sent_total_gb': bandwidth_sent_total_gb, 'bandwidth_recv_total_gb': bandwidth_recv_total_gb,
        'bandwidth_sent_total_tb': bandwidth_sent_total_tb, 'bandwidth_recv_total_tb': bandwidth_recv_total_tb,
        'net_speed': net_speed, 'uptime': uptime_seconds, 'connections': connections,
        'server_time': server_time, 'timezone': timezone, 'boot_time': boot_time
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
