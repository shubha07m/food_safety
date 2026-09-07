import io

import pytest

from food_safety.config import Settings
from food_safety.fetch import Fetcher, FetchError


class Response:
    def __init__(self, body=b"<article>fixture</article>", status=200, headers=None):
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = {"Content-Type": "text/html", **(headers or {})}

    def getheader(self, key, default=None):
        return self.headers.get(key, default)

    def read(self, size):
        return self.body.read(size)


@pytest.fixture
def fetch_mock(monkeypatch, policy):
    import food_safety.fetch as module

    monkeypatch.setattr(module, "public_addresses", lambda *a: ["8.8.8.8"])
    responses = []
    connections = []

    class Connection:
        def __init__(self, host, ip, port, timeout):
            self.host, self.ip, self.closed = host, ip, False
            connections.append(self)

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return responses.pop(0)

        def close(self):
            self.closed = True

    monkeypatch.setattr(module, "PinnedHTTPS", Connection)
    monkeypatch.setattr(module, "PinnedHTTP", Connection)
    return Fetcher([policy], Settings(max_response_bytes=1024)), responses, connections


def test_bounded_body_and_ip_pin(fetch_mock):
    fetcher, responses, connections = fetch_mock
    responses.append(Response())
    assert "fixture" in fetcher.raw("https://example.org/fixture")[1]
    assert connections[0].ip == "8.8.8.8"
    assert connections[0].host == "example.org"
    assert connections[0].closed


@pytest.mark.parametrize(
    "response,reason",
    [
        (Response(b"x" * 1025), "response_too_large"),
        (Response(headers={"Content-Length": "2000"}), "response_too_large"),
        (Response(headers={"Content-Encoding": "gzip"}), "compressed_response"),
        (Response(headers={"Content-Type": "application/pdf"}), "unsupported_content_type"),
        (Response(status=403), "http_403"),
        (Response(status=302, headers={"Location": "http://127.0.0.1/private"}), "private_url"),
        (
            Response(status=302, headers={"Location": "http://example.org/plain"}),
            "insecure_redirect",
        ),
        (
            Response(status=302, headers={"Location": "https://unknown.example/article"}),
            "domain_not_enabled",
        ),
    ],
)
def test_response_and_redirect_fail_closed(fetch_mock, response, reason):
    fetcher, responses, connections = fetch_mock
    responses.append(response)
    with pytest.raises(ValueError, match=reason):
        fetcher.raw("https://example.org/fixture")
    assert all(c.closed for c in connections)


def test_robots_denial(fetch_mock):
    fetcher, responses, connections = fetch_mock
    responses.append(
        Response(b"User-agent: *\nDisallow: /\n", headers={"Content-Type": "text/plain"})
    )
    with pytest.raises(FetchError, match="robots_disallowed"):
        fetcher.article("https://example.org/fixture")
    assert len(connections) == 1


def test_robots_unavailable(fetch_mock):
    fetcher, responses, connections = fetch_mock
    responses.append(Response(status=404))
    with pytest.raises(FetchError, match="http_404"):
        fetcher.article("https://example.org/fixture")
    assert len(connections) == 1
