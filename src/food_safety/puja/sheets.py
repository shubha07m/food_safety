"""Local desktop OAuth and read-only Form response sync. Never used by Actions."""

import json
import re
from functools import partial
from urllib.parse import quote

import httpx

from .queue_store import ingest_responses

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
PRIVATE = ".cache/puja"


def oauth_types():
    # Optional operator dependency: public builds never need Google auth libraries.
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    return Credentials, Request, RefreshError, InstalledAppFlow


def credentials(root):
    Credentials, Request, RefreshError, InstalledAppFlow = oauth_types()
    folder = root / PRIVATE
    client_file, token_file = folder / "oauth-client.json", folder / "oauth-token.json"
    if not client_file.exists():
        raise ValueError("Desktop OAuth client missing; see docs/PUJA_CURATION.md")
    client = json.loads(client_file.read_text())
    if "installed" not in client:
        raise ValueError("Desktop OAuth client required")
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if creds.scopes != SCOPES or creds.client_id != client["installed"]["client_id"]:
            creds = None
    if creds and not creds.valid and creds.refresh_token:
        try:
            creds.refresh(partial(Request(), timeout=20))
        except RefreshError:
            creds = None
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_config(client, SCOPES, autogenerate_code_verifier=True)
        creds = flow.run_local_server(
            host="127.0.0.1",
            port=0,
            open_browser=True,
            timeout_seconds=120,
            authorization_prompt_message="Authorize read-only Puja Sheet access in your browser.",
            success_message="Authorization complete. You can close this tab.",
            access_type="offline",
            prompt="consent",
        )
    # Create with restrictive permissions before writing any token bytes.
    import os

    temporary = token_file.with_suffix(".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(creds.to_json())
    temporary.chmod(0o600)
    temporary.replace(token_file)
    return creds


def read_responses(root):
    config = json.loads((root / PRIVATE / "sheet.json").read_text())
    sheet_id = config["spreadsheet_id"]
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", sheet_id):
        raise ValueError("Invalid Sheet ID")
    tab = config.get("response_tab", "Form Responses 1")
    if not isinstance(tab, str) or not 0 < len(tab) <= 100:
        raise ValueError("Invalid response tab")
    creds = credentials(root)
    # Fixed bounded range includes header and the first 10,000 responses.
    area = "'" + tab.replace("'", "''") + "'!A1:Z10002"
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{quote(area, safe='')}"
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False) as client:
        with client.stream("GET", url, headers={"Authorization": "Bearer " + creds.token}) as r:
            r.raise_for_status()
            body = bytearray()
            for chunk in r.iter_bytes():
                body.extend(chunk)
                if len(body) > 4 * 1024 * 1024:
                    raise ValueError("Sheet response too large")
    values = json.loads(body).get("values", [])
    if len(values) > 10001:
        raise ValueError("Sheet exceeds 10,000 responses; existing queue retained")
    if not values:
        return []
    headers = [str(v).strip() for v in values[0]]
    return [dict(zip(headers, row, strict=False)) for row in values[1:]]


def sync(root, reader=read_responses):
    """Failures are visible, but never stop the offline review page."""
    try:
        result = ingest_responses(root, reader(root))
        return f"Sheet synced: {result['new']} new response(s)."
    except Exception as exc:
        # Never print provider exceptions, headers, Sheet rows or OAuth content.
        return (
            f"Sheet sync unavailable ({type(exc).__name__}); using local queue. "
            "Setup: docs/PUJA_CURATION.md"
        )
