"""Blizzard Game Data API client for EU auction house scans."""

from __future__ import annotations

import re
import time
from typing import Any

import requests

EU_API_HOST = "https://eu.api.blizzard.com"
OAUTH_URL = "https://oauth.battle.net/token"
NAMESPACE = "dynamic-eu"
LOCALE = "en_GB"

CR_ID_RE = re.compile(r"/data/wow/connected-realm/(\d+)")


class BlizzardClient:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._session = requests.Session()

    def _ensure_token(self) -> None:
        if self._token:
            return

        resp = self._session.post(
            OAUTH_URL,
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            timeout=30,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]

    def _get(self, path: str, retries: int = 3) -> dict[str, Any]:
        self._ensure_token()
        url = f"{EU_API_HOST}{path}"
        params = {
            "namespace": NAMESPACE,
            "locale": LOCALE,
        }
        headers = {"Authorization": f"Bearer {self._token}"}

        for attempt in range(retries):
            resp = self._session.get(url, params=params, headers=headers, timeout=120)
            if resp.status_code == 401:
                self._token = None
                self._ensure_token()
                headers["Authorization"] = f"Bearer {self._token}"
                continue
            if resp.status_code == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            data = resp.json()
            if data is None:
                raise ValueError(f"Empty response from {path}")
            return data

        raise RuntimeError(f"Failed to fetch {path} after {retries} retries")

    def get_connected_realm_ids(self) -> list[int]:
        index = self._get("/data/wow/connected-realm/index")
        ids: list[int] = []
        for cr in index.get("connected_realms", []):
            match = CR_ID_RE.search(cr.get("href", ""))
            if match:
                ids.append(int(match.group(1)))
        return ids

    def get_connected_realm_realms(self, connected_realm_id: int) -> list[dict[str, Any]]:
        data = self._get(f"/data/wow/connected-realm/{connected_realm_id}")
        return data.get("realms", [])

    def get_auctions(self, connected_realm_id: int) -> list[dict[str, Any]]:
        data = self._get(f"/data/wow/connected-realm/{connected_realm_id}/auctions")
        return data.get("auctions") or []
