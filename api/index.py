import os
import sys

# Add project root to sys.path so 'app' can be imported by Python serverless runner
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app


class VercelPathMiddleware:
    """
    Pure ASGI middleware that normalizes request paths for Vercel Serverless Functions
    without buffering or interfering with request streams (preserving multipart file uploads).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "")
            headers = dict(scope.get("headers", []))
            matched_path = headers.get(b"x-matched-path", b"").decode("utf-8")

            # If Vercel passed the serverless script path, recover original matched route
            if path in ("/api/index.py", "/api/index", "/api") and matched_path:
                scope["path"] = matched_path
            elif path.startswith("/api/index.py/"):
                scope["path"] = path[len("/api/index.py"):]
            elif path.startswith("/api/") and not path.startswith("/api/report"):
                scope["path"] = path[len("/api"):]

        await self.app(scope, receive, send)


# Wrap FastAPI app with the pure ASGI middleware
app = VercelPathMiddleware(app)

