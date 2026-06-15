from dataclasses import dataclass
from typing import Any

import requests


class ShlinkError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class ShlinkConflict(ShlinkError):
    pass


class ShlinkUnavailable(ShlinkError):
    pass


@dataclass
class ShlinkClient:
    base_url: str
    api_key: str
    domain: str
    timeout: float = 12
    verify_tls: bool = True

    def __post_init__(self):
        self.base_url = self.base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Api-Key": self.api_key,
                "User-Agent": "Sagar-Link-Analytics/2.0",
            }
        )

    def _request(self, method: str, path: str, **kwargs):
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                timeout=self.timeout,
                verify=self.verify_tls,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise ShlinkUnavailable(f"Shlink is not reachable: {exc}") from exc

        payload = None
        if response.content:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
        message = self._error_message(payload, f"Shlink returned HTTP {response.status_code}.")
        duplicate_hint = message.lower()
        if response.status_code in {409, 422} or (
            response.status_code == 400
            and any(term in duplicate_hint for term in ("already", "in use", "custom slug"))
        ):
            raise ShlinkConflict(message, response.status_code, payload)
        if response.status_code >= 400:
            raise ShlinkError(message, response.status_code, payload)
        return payload

    @staticmethod
    def _error_message(payload, fallback):
        if isinstance(payload, dict):
            return payload.get("detail") or payload.get("message") or payload.get("title") or fallback
        return fallback

    def health(self):
        for path in ("/rest/health", "/rest/v3/health"):
            try:
                return self._request("GET", path)
            except ShlinkError as exc:
                if exc.status_code != 404:
                    raise
        raise ShlinkError("Shlink health endpoint was not found.")

    def create_short_url(self, long_url: str, custom_slug: str):
        return self._request(
            "POST",
            "/rest/v3/short-urls",
            json={
                "longUrl": long_url,
                "customSlug": custom_slug,
                "domain": self.domain,
                "validateUrl": True,
                "findIfExists": False,
            },
        )

    def list_short_urls(self, page: int = 1, items_per_page: int = 500):
        payload = self._request(
            "GET",
            "/rest/v3/short-urls",
            params={"page": page, "itemsPerPage": items_per_page, "orderBy": "dateCreated-DESC"},
        )
        if isinstance(payload, dict):
            container = payload.get("shortUrls", payload)
            if isinstance(container, dict):
                return container.get("data", [])
            if isinstance(container, list):
                return container
        return []

    def get_short_url(self, short_code: str):
        return self._request(
            "GET", f"/rest/v3/short-urls/{short_code}", params={"domain": self.domain}
        )

    def update_short_url(self, short_code: str, long_url: str):
        return self._request(
            "PATCH",
            f"/rest/v3/short-urls/{short_code}",
            params={"domain": self.domain},
            json={"longUrl": long_url},
        )

    def delete_short_url(self, short_code: str):
        return self._request(
            "DELETE", f"/rest/v3/short-urls/{short_code}", params={"domain": self.domain}
        )

    def get_visits(self, short_code: str, page: int = 1, items_per_page: int = 1000):
        payload = self._request(
            "GET",
            f"/rest/v3/short-urls/{short_code}/visits",
            params={
                "domain": self.domain,
                "page": page,
                "itemsPerPage": items_per_page,
                "excludeBots": "false",
            },
        )
        if isinstance(payload, dict):
            container = payload.get("visits", payload)
            if isinstance(container, dict):
                return container.get("data", [])
            if isinstance(container, list):
                return container
        return []
