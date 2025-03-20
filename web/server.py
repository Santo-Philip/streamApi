from aiohttp import web
import psutil
import asyncio


async def get_server_stats():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    net = psutil.net_io_counters()
    bandwidth_sent = net.bytes_sent / 1024 / 1024  # MB
    bandwidth_recv = net.bytes_recv / 1024 / 1024  # MB
    return {
        'cpu': cpu,
        'ram': ram,
        'disk': disk,
        'bandwidth_sent': bandwidth_sent,
        'bandwidth_recv': bandwidth_recv
    }

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # Send stats every 2 seconds
    while not ws.closed:
        stats = await get_server_stats()
        await ws.send_json(stats)
        await asyncio.sleep(2)

    return ws

async def index_handler(request):
    # Serve the HTML page with the graph
    with open('server.html', 'r') as f:
        return web.Response(text=f.read(), content_type='text/html')
