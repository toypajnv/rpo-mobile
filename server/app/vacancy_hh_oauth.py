"""Official HH OAuth application token acquisition and refresh."""
from __future__ import annotations

import json
import os
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

_cache = {"token": "", "expires_at": 0.0}

def get_access_token() -> str:
    static_token = os.getenv("HH_API_TOKEN", "").strip()
    if static_token:
        return static_token
    client_id = os.getenv("HH_CLIENT_ID", "").strip()
    secret = os.getenv("HH_CLIENT_SECRET", "").strip()
    if not client_id or not secret:
        raise RuntimeError("HeadHunter: для поиска требуется HH_API_TOKEN или HH_CLIENT_ID и HH_CLIENT_SECRET зарегистрированного приложения.")
    if _cache["token"] and _cache["expires_at"] > time.time() + 120:
        return _cache["token"]
    data = urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": secret,
    }).encode("utf-8")
    req = Request("https://api.hh.ru/token", data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "HH-User-Agent": os.getenv("HH_USER_AGENT", "RPOVacancyMonitor/2.0 (rpo@rpo-mng.ru)"),
    }, method="POST")
    try:
        with urlopen(req, timeout=20) as response:
            token_data = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"HH OAuth: HTTP {exc.code}. Проверьте ключи зарегистрированного приложения.") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("HH OAuth: сервер авторизации недоступен.") from exc
    token = token_data.get("access_token", "")
    if not isinstance(token, str) or not token:
        raise RuntimeError("HH OAuth не вернул access_token")
    _cache["token"] = token
    _cache["expires_at"] = time.time() + int(token_data.get("expires_in", 3600))
    return token
