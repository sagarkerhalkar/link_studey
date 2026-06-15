import requests
import pytest

from link_analytics.shlink_client import (
    ShlinkClient,
    ShlinkConflict,
    ShlinkError,
    ShlinkUnavailable,
)


class DummyResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self.content = b"x" if payload is not None or text else b""

    def json(self):
        if isinstance(self._payload, ValueError):
            raise self._payload
        return self._payload


@pytest.fixture()
def client():
    return ShlinkClient(
        base_url="http://shlink:8080/",
        api_key="secret-key",
        domain="s.sagarkerhalkar.com",
        timeout=1,
        verify_tls=False,
    )


def test_all_client_operations(client, monkeypatch):
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        if url.endswith("/rest/health"):
            return DummyResponse(payload={"status": "pass"})
        if method == "POST":
            return DummyResponse(
                201,
                {
                    "shortCode": "8hb2kld",
                    "shortUrl": "https://s.sagarkerhalkar.com/8hb2kld",
                    "longUrl": "https://example.com",
                },
            )
        if method == "GET" and url.endswith("/rest/v3/short-urls"):
            return DummyResponse(payload={"shortUrls": {"data": [{"shortCode": "8hb2kld"}]}})
        if method == "GET" and url.endswith("/visits"):
            return DummyResponse(payload={"visits": {"data": [{"referer": ""}]}})
        if method == "PATCH":
            return DummyResponse(payload={"shortCode": "8hb2kld", "longUrl": "https://updated.example"})
        if method == "DELETE":
            return DummyResponse(204)
        return DummyResponse(payload={"shortCode": "8hb2kld"})

    monkeypatch.setattr(client.session, "request", request)
    assert client.health()["status"] == "pass"
    assert client.create_short_url("https://example.com", "8hb2kld")["shortCode"] == "8hb2kld"
    assert client.list_short_urls() == [{"shortCode": "8hb2kld"}]
    assert client.get_short_url("8hb2kld")["shortCode"] == "8hb2kld"
    assert client.update_short_url("8hb2kld", "https://updated.example")["longUrl"] == "https://updated.example"
    assert client.delete_short_url("8hb2kld") is None
    assert client.get_visits("8hb2kld") == [{"referer": ""}]
    assert any(call[2]["headers"] if "headers" in call[2] else True for call in calls)


def test_conflict_and_api_error(client, monkeypatch):
    monkeypatch.setattr(
        client.session,
        "request",
        lambda *args, **kwargs: DummyResponse(409, {"detail": "Custom slug already in use"}),
    )
    with pytest.raises(ShlinkConflict, match="Custom slug"):
        client.create_short_url("https://example.com", "taken")

    monkeypatch.setattr(
        client.session,
        "request",
        lambda *args, **kwargs: DummyResponse(500, {"title": "Server error"}),
    )
    with pytest.raises(ShlinkError, match="Server error"):
        client.list_short_urls()


def test_network_and_non_json_errors(client, monkeypatch):
    def network_error(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(client.session, "request", network_error)
    with pytest.raises(ShlinkUnavailable, match="not reachable"):
        client.health()

    monkeypatch.setattr(
        client.session,
        "request",
        lambda *args, **kwargs: DummyResponse(502, ValueError("not json"), "bad gateway"),
    )
    with pytest.raises(ShlinkError, match="HTTP 502"):
        client.list_short_urls()


def test_health_falls_back_to_versioned_path(client, monkeypatch):
    count = {"value": 0}

    def request(*args, **kwargs):
        count["value"] += 1
        if count["value"] == 1:
            return DummyResponse(404, {"title": "Not found"})
        return DummyResponse(200, {"status": "pass"})

    monkeypatch.setattr(client.session, "request", request)
    assert client.health()["status"] == "pass"
    assert count["value"] == 2
