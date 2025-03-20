from aiohttp import web
import psutil
import asyncio
import os
import json
import time
import platform
import sqlite3
from datetime import datetime, timedelta

# SQLite3 Setup - Dynamic path
DB_FILE = os.path.join(os.path.dirname(__file__), 'server_stats.db')


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Main stats table
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
    # Daily bandwidth summary table
    c.execute('''CREATE TABLE IF NOT EXISTS bandwidth_daily (
        date TEXT PRIMARY KEY,
        sent_total REAL,
        recv_total REAL
    )''')
    conn.commit()
    conn.close()


async def get_server_stats(selected_date=None):
    if selected_date:
        # Fetch historical data for the selected date
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        start_time = int(time.mktime(datetime.strptime(selected_date, '%Y-%m-%d').timetuple()))
        end_time = start_time + 86400  # One day
        c.execute('''SELECT AVG(cpu), AVG(cpu_count), AVG(cpu_speed), AVG(cpu_temp), AVG(load_avg),
                            AVG(ram), AVG(ram_used), AVG(ram_total), AVG(disk), AVG(disk_used), AVG(disk_total),
                            AVG(bandwidth_sent_total), AVG(bandwidth_recv_total), AVG(net_speed), AVG(connections)
                     FROM stats WHERE timestamp >= ? AND timestamp < ?''', (start_time, end_time))
        row = c.fetchone()
        c.execute('SELECT sent_total, recv_total FROM bandwidth_daily WHERE date = ?', (selected_date,))
        bandwidth_row = c.fetchone()
        conn.close()

        if row and bandwidth_row:
            return {
                'cpu': row[0] or 0, 'cpu_count': int(row[1] or 0), 'cpu_speed': row[2] or 0, 'cpu_temp': row[3] or 0,
                'load_avg': row[4] or 0, 'ram': row[5] or 0, 'ram_used_gb': row[6] or 0, 'ram_total_gb': row[7] or 0,
                'disk': row[8] or 0, 'disk_used_gb': row[9] or 0, 'disk_total_gb': row[10] or 0,
                'bandwidth_sent_total_mb': row[11] or 0, 'bandwidth_recv_total_mb': row[12] or 0,
                'net_speed': row[13] or 0, 'connections': int(row[14] or 0),
                'daily_sent_mb': bandwidth_row[0] or 0, 'daily_recv_mb': bandwidth_row[1] or 0,
                'server_time': selected_date, 'timezone': time.tzname[0], 'boot_time': 'N/A', 'uptime': 0
            }
        return None

    # Live data
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq() or psutil._common.scpufreq(0, 0, 0)
    cpu_speed = cpu_freq.current / 1000 if cpu_freq.current else 0
    cpu_temp = psutil.sensors_temperatures().get('coretemp', [None])[0].current if psutil.sensors_temperatures().get(
        'coretemp') else 0
    load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)

    ram = psutil.virtual_memory()
    ram_used_mb = ram.used / 1024 / 1024
    ram_total_mb = ram.total / 1024 / 1024
    ram_used_gb = ram.used / 1024 / 1024 / 1024
    ram_total_gb = ram.total / 1024 / 1024 / 1024
    ram_used_tb = ram.used / 1024 / 1024 / 1024 / 1024
    ram_total_tb = ram.total / 1024 / 1024 / 1024 / 1024

    disk = psutil.disk_usage('/')
    disk_used_mb = disk.used / 1024 / 1024
    disk_total_mb = disk.total / 1024 / 1024
    disk_used_gb = disk.used / 1024 / 1024 / 1024
    disk_total_gb = disk.total / 1024 / 1024 / 1024
    disk_used_tb = disk.used / 1024 / 1024 / 1024 / 1024
    disk_total_tb = disk.total / 1024 / 1024 / 1024 / 1024

    net = psutil.net_io_counters()
    bandwidth_sent_total_mb = net.bytes_sent / 1024 / 1024
    bandwidth_recv_total_mb = net.bytes_recv / 1024 / 1024
    bandwidth_sent_total_gb = net.bytes_sent / 1024 / 1024 / 1024
    bandwidth_recv_total_gb = net.bytes_recv / 1024 / 1024 / 1024
    bandwidth_sent_total_tb = net.bytes_sent / 1024 / 1024 / 1024 / 1024
    bandwidth_recv_total_tb = net.bytes_recv / 1024 / 1024 / 1024 / 1024

    # Fixed Network Speed
    net_stats = psutil.net_if_stats()
    net_speed = 0
    for interface, stats in net_stats.items():
        if stats.isup and stats.speed > 0:  # Use first active interface with a valid speed
            net_speed = stats.speed / 1000  # Convert Mbps to Gbps
            break

    connections = len(psutil.net_connections())
    uptime_seconds = time.time() - psutil.boot_time()
    server_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    timezone = time.tzname[0] if time.tzname else "Unknown"
    boot_time = datetime.fromtimestamp(psutil.boot_time()).strftime('%Y-%m-%d %H:%M:%S')

    # Update daily bandwidth
    today = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO bandwidth_daily (date, sent_total, recv_total) VALUES (?, ?, ?)',
              (today, bandwidth_sent_total_mb, bandwidth_recv_total_mb))

    # Store live stats
    c.execute('''INSERT INTO stats (timestamp, cpu, cpu_count, cpu_speed, cpu_temp, load_avg, ram, ram_used, ram_total, 
                 disk, disk_used, disk_total, bandwidth_sent_total, bandwidth_recv_total, net_speed, connections)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (int(time.time()), cpu_percent, cpu_count, cpu_speed, cpu_temp, load_avg[0], ram.percent,
               ram_used_gb, ram_total_gb, disk.percent, disk_used_gb, disk_total_gb,
               bandwidth_sent_total_mb, bandwidth_recv_total_mb, net_speed, connections))
    conn.commit()
    conn.close()

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
        'daily_sent_mb': bandwidth_sent_total_mb, 'daily_recv_mb': bandwidth_recv_total_mb,
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


init_db()