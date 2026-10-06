import os
import time
from typing import Dict, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

SANDBOX_AUTH_URL = "https://api.sandbox.co.in/authenticate"
DEFAULT_API_KEY = "key_live_01773eb1b44b400ebce0b4ea52378559"
DEFAULT_API_SECRET = "secret_live_f5f69cfc5b57437eb836d17fd93f8c98"

# In-memory token cache: { "token": str, "expires_at": float }
_token_cache: Dict[str, Optional[object]] = {
    "token": None,
    "expires_at": 0.0,
}


def get_sandbox_credentials():
    api_key = os.getenv("SANDBOX_API_KEY", DEFAULT_API_KEY)
    api_secret = os.getenv("SANDBOX_API_SECRET", DEFAULT_API_SECRET)
    return api_key, api_secret


def get_sandbox_token(force_refresh: bool = False, timeout: int = 10) -> str:
    """
    Authenticate against Sandbox.co.in and obtain an access token.
    Caches the token in memory to avoid redundant authentication requests.
    """
    now = time.time()
    cached_token = _token_cache.get("token")
    expires_at = _token_cache.get("expires_at", 0.0)

    # If valid cached token exists with at least 5 minutes remaining
    if not force_refresh and cached_token and isinstance(cached_token, str) and (expires_at - now > 300):
        return cached_token

    api_key, api_secret = get_sandbox_credentials()
    headers = {
        "x-api-key": api_key,
        "x-api-secret": api_secret,
        "x-api-version": "1.0.0",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(SANDBOX_AUTH_URL, headers=headers, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        token = data.get("data", {}).get("access_token") or data.get("access_token")

        if not token:
            raise ValueError(f"No access token returned from Sandbox auth: {data}")

        # Sandbox tokens are valid for 24h (86400s). Default expiry to now + 23 hours.
        _token_cache["token"] = token
        _token_cache["expires_at"] = now + 82800.0
        return token
    except requests.exceptions.Timeout:
        raise TimeoutError("Timeout while authenticating with Sandbox API")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to authenticate with Sandbox API: {str(e)}")


def get_sandbox_headers(api_version: str = "1.0.0", timeout: int = 10) -> Dict[str, str]:
    """
    Return standard headers for calling Sandbox APIs with a valid access token.
    """
    token = get_sandbox_token(timeout=timeout)
    api_key, _ = get_sandbox_credentials()
    return {
        "authorization": token,
        "x-api-key": api_key,
        "x-api-version": api_version,
        "Content-Type": "application/json",
    }
