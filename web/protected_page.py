from aiohttp import web
import base64

USERNAME = "admin"
PASSWORD = "password"

async def check_auth(request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Basic "):
        print("No or invalid Authorization header")
        return False
    try:
        encoded = auth_header.split(" ")[1]
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
        is_valid = username == USERNAME and password == PASSWORD
        print(f"Auth check: {username} - Valid? {is_valid}")
        return is_valid
    except Exception as e:
        print(f"Auth error: {str(e)}")
        return False

@web.middleware
async def auth_middleware(request, handler):
    if not await check_auth(request):
        return web.Response(
            status=401,
            text="Unauthorized",
            headers={"WWW-Authenticate": 'Basic realm="Secure Area"'}
        )
    return await handler(request)
