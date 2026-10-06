import os
import sys
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

class VercelPrefixMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith('/api/index.py'):
            subpath = path[len('/api/index.py'):] or '/'
            request.scope['path'] = subpath
        elif path.startswith('/api/') and not path.startswith('/api/report'):
            subpath = path[len('/api'):]
            request.scope['path'] = subpath
        return await call_next(request)

app.add_middleware(VercelPrefixMiddleware)
