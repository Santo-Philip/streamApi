from aiohttp import web
import psutil
import asyncio
import os
import json
import time
import platform
import sqlite3
from datetime import datetime

# SQLite3 Setup - Dynamic path based on server.py location
DB_FILE = os.path.join(os.path.dirname(__file__), 'server_stats.db')

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
        timestamp INTEGER,
        cpu REAL,
        cpu_count INTEGER,
        cpu_speed REAL,
        cpu_temp REAL,
        load_avg REAL,
        ram REAL,
        ram_used REAL,
        ram_total REAL,
        disk REAL,
        disk_used REAL,
        disk_total REAL,
        bandwidth_sent_total REAL,
        bandwidth_recv_total REAL,
        net_speed REAL,
        connections INTEGER
    )''')
    conn.commit()
    conn.close()

async def get_server_stats():
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq() or psutil._common.scpufreq(0, 0, 0)
    cpu_speed = cpu_freq.current / 1000 if cpu_freq.current else 0  # GHz
    cpu_model = platform.processor() or "Unknown"
    cpu_temp = psutil.sensors_temperatures().get('coretemp', [None])[0].current if psutil.sensors_temperatures().get('coretemp') else 0
    load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)

    # RAM
    ram = psutil.virtual_memory()
    ram_used_mb = ram.used / 1024 / 1024  # MB
    ram_total_mb = ram.total / 1024 / 1024  # MB
    ram_used_gb = ram.used / 1024 / 1024 / 1024  # GB
    ram_total_gb = ram.total / 1024 / 1024 / 1024  # GB
    ram_used_tb = ram.used / 1024 / 1024 / 1024 / 1024  # TB
    ram_total_tb = ram.total / 1024 / 1024 / 1024 / 1024  # TB

    # Disk
    disk = psutil.disk_usage('/')
    disk_used_mb = disk.used / 1024 / 1024  # MB
    disk_total_mb = disk.total / 1024 / 1024  # MB
    disk_used_gb = disk.used / 1024 / 1024 / 1024  # GB
    disk_total_gb = disk.total / 1024 / 1024 / 1024  # GB
    disk_used_tb = disk.used / 1024 / 1024 / 1024 / 1024  # TB
    disk_total_tb = disk.total / 1024 / 1024 / 1024 / 1024  # TB

    # Bandwidth
    net = psutil.net_io_counters()
    bandwidth_sent_total_mb = net.bytes_sent / 1024 / 1024  # MB
    bandwidth_recv_total_mb = net.bytes_recv / 1024 / 1024  # MB
    bandwidth_sent_total_gb = net.bytes_sent / 1024 / 1024 / 1024  # GB
    bandwidth_recv_total_gb = net.bytes_recv / 1024 / 1024 / 1024  # GB
    bandwidth_sent_total_tb = net.bytes_sent / 1024 / 1024 / 1024 / 1024  # TB
    bandwidth_recv_total_tb = net.bytes_recv / 1024 / 1024 / 1024 / 1024  # TB
    # Network speed (fixed)
    net_stats = psutil.net_if_stats()
    default_interface = next(iter(net_stats), None)
    net_speed = net_stats[default_interface].speed / 1000 if default_interface and net_stats[default_interface].speed else 0  # Gbps

    # Uptime
    uptime_seconds = time.time() - psutil.boot_time()

    # Connections
    connections = len(psutil.net_connections())

    # Time Details
    server_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    timezone = time.tzname[0] if time.tzname else "Unknown"
    boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')

    stats = {
        'cpu': cpu_percent,
        'cpu_count': cpu_count,
        'cpu_speed': cpu_speed,
        'cpu_model': cpu_model,
        'cpu_temp': cpu_temp,
        'load_avg': load_avg[0],
        'ram': ram.percent,
        'ram_used_mb': ram_used_mb,
        'ram_total_mb': ram_total_mb,
        'ram_used_gb': ram_used_gb,
        'ram_total_gb': ram_total_gb,
        'ram_used_tb': ram_used_tb,
        'ram_total_tb': ram_total_tb,
        'disk': disk.percent,
        'disk_used_mb': disk_used_mb,
        'disk_total_mb': disk_total_mb,
        'disk_used_gb': disk_used_gb,
        'disk_total_gb': disk_total_gb,
        'disk_used_tb': disk_used_tb,
        'disk_total_tb': disk_total_tb,
        'bandwidth_sent_total_mb': bandwidth_sent_total_mb,
        'bandwidth_recv_total_mb': bandwidth_recv_total_mb,
        'bandwidth_sent_total_gb': bandwidth_sent_total_gb,
        'bandwidth_recv_total_gb': bandwidth_recv_total_gb,
        'bandwidth_sent_total_tb': bandwidth_sent_total_tb,
        'bandwidth_recv_total_tb': bandwidth_recv_total_tb,
        'net_speed': net_speed,
        'uptime': uptime_seconds,
        'connections': connections,
        'server_time': server_time,
        'timezone': timezone,
        'boot_time': boot_time
    }

    # Store in SQLite
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''INSERT INTO stats (timestamp, cpu, cpu_count, cpu_speed, cpu_temp, load_avg, ram, ram_used, ram_total, 
                 disk, disk_used, disk_total, bandwidth_sent_total, bandwidth_recv_total, net_speed, connections)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (int(time.time()), stats['cpu'], stats['cpu_count'], stats['cpu_speed'], stats['cpu_temp'], stats['load_avg'],
               stats['ram'], stats['ram_used_gb'], stats['ram_total_gb'], stats['disk'], stats['disk_used_gb'], stats['disk_total_gb'],
               stats['bandwidth_sent_total_mb'], stats['bandwidth_recv_total_mb'], stats['net_speed'], stats['connections']))
    conn.commit()
    conn.close()

    return stats

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


init_db()