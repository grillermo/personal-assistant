import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import requests
from playwright.sync_api import sync_playwright

REDIRECT_URI = "http://localhost:8080"
AUTH_URL = "https://auth.mercadolibre.com.mx/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
DEV_PORTAL_URL = "https://developers.mercadolibre.com.mx/en_us/application-manager"


def parse_oauth_code(path: str) -> Optional[str]:
    params = parse_qs(urlparse(path).query)
    codes = params.get("code")
    return codes[0] if codes else None
