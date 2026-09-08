"""Bounded read-only canonical deployment/header check; no secrets or bodies logged."""

import httpx

URL = "https://foodsafety.nemoneek.com/"


def main():
    expected = {
        "content-security-policy": "frame-ancestors 'none'",
        "strict-transport-security": "max-age=",
        "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer",
        "permissions-policy": "camera=()",
    }
    with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
        response = client.head(URL)
    if response.status_code != 200:
        raise SystemExit(f"Canonical site returned HTTP {response.status_code}")
    missing = [key for key, value in expected.items() if value not in response.headers.get(key, "")]
    if missing:
        raise SystemExit("Missing/incorrect security headers: " + ", ".join(missing))
    print("Canonical HTTPS deployment and security headers passed.")


if __name__ == "__main__":
    main()
