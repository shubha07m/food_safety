"""Small, DNS-pinned HTTP fetches: no proxies, scripts, cookies or arbitrary domains."""

import http.client
import ipaddress
import socket
import ssl
import time
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from .safety import safe_url

USER_AGENT = "WBFSEvidenceResearch/0.2 (limited public-source research)"


class FetchError(ValueError):
    pass


def public_addresses(host, port):
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = sorted({info[4][0] for info in infos})
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise FetchError("private_dns_destination")
    return addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip, port, timeout):
        super().__init__(host, port=port, timeout=timeout, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.host)


class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, ip, port, timeout):
        super().__init__(host, port=port, timeout=timeout)
        self.ip = ip

    def connect(self):
        self.sock = socket.create_connection((self.ip, self.port), self.timeout)


class Fetcher:
    def __init__(self, policies, settings):
        self.domains = {p.domain for p in policies if p.enabled and p.tier != "discovery"}
        self.settings = settings
        self.robots = {}

    def raw(self, url, redirects=0, check_redirect_robots=False):
        url = safe_url(url)
        parsed = urlsplit(url)
        if parsed.hostname not in self.domains:
            raise FetchError("domain_not_enabled")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        ips = public_addresses(parsed.hostname, port)
        cls = PinnedHTTPS if parsed.scheme == "https" else PinnedHTTP
        connection = cls(parsed.hostname, ips[0], port, self.settings.request_timeout_seconds)
        started = time.monotonic()
        try:
            path = parsed.path + ("?" + parsed.query if parsed.query else "")
            connection.request(
                "GET",
                path,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept-Encoding": "identity",
                    "Accept": "text/html,text/plain,application/xhtml+xml",
                },
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                if redirects >= 3 or not response.getheader("Location"):
                    raise FetchError("redirect_limit")
                target = safe_url(urljoin(url, response.getheader("Location")))
                if parsed.scheme == "https" and urlsplit(target).scheme != "https":
                    raise FetchError("insecure_redirect")
                if check_redirect_robots:
                    self.allowed(target)
                return self.raw(target, redirects + 1, check_redirect_robots)
            if response.status != 200:
                error = FetchError(f"http_{response.status}")
                raw_retry = response.getheader("Retry-After")
                if raw_retry:
                    try:
                        error.retry_after = (
                            (datetime.now(UTC) + timedelta(seconds=int(raw_retry)))
                            if raw_retry.isdigit()
                            else parsedate_to_datetime(raw_retry)
                        )
                    except (ValueError, TypeError, OverflowError):
                        pass
                raise error
            if response.getheader("Content-Encoding", "identity") != "identity":
                raise FetchError("compressed_response_rejected")
            content_type = response.getheader("Content-Type", "").split(";")[0].lower()
            if content_type not in {
                "text/html",
                "text/plain",
                "application/xhtml+xml",
                "application/rss+xml",
                "application/atom+xml",
                "application/xml",
                "text/xml",
            }:
                raise FetchError("unsupported_content_type")
            limit = self.settings.max_response_bytes
            length = response.getheader("Content-Length")
            if length and int(length) > limit:
                raise FetchError("response_too_large")
            body = bytearray()
            while len(body) <= limit:
                if time.monotonic() - started > self.settings.request_timeout_seconds:
                    raise FetchError("request_deadline")
                chunk = response.read(min(8192, limit + 1 - len(body)))
                if not chunk:
                    break
                body.extend(chunk)
            if len(body) > limit:
                raise FetchError("response_too_large")
            return url, body.decode("utf-8", errors="replace")
        finally:
            connection.close()

    def allowed(self, url):
        url = safe_url(url)
        parsed = urlsplit(url)
        if parsed.hostname not in self.domains:
            raise FetchError("domain_not_enabled")
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self.robots:
            _, body = self.raw(origin + "/robots.txt")
            parser = RobotFileParser()
            parser.parse(body.splitlines())
            self.robots[origin] = parser
        parser = self.robots[origin]
        if not parser.can_fetch(USER_AGENT, url):
            raise FetchError("robots_disallowed")
        if parser.crawl_delay(USER_AGENT) or parser.request_rate(USER_AGENT):
            raise FetchError("robots_rate_policy_requires_review")

    def article(self, url):
        self.allowed(url)
        return self.raw(url, check_redirect_robots=True)
