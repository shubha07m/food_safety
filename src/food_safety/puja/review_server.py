"""Local-only Puja editorial cards. The browser never receives GitHub credentials."""

import html
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .approvals import submit_approval
from .review_queue import candidates, compile_record, save_decision


def _escape(value):
    return html.escape(str(value or ""), quote=True)


def _present(facts, key):
    return bool((facts.get(key) or {}).get("value"))


def render(root, nonce, notice=""):
    rows = candidates(root)
    cards = []
    for item in rows:
        facts = item.get("fields", {})
        flags = [
            ("Organizer source", item.get("source_type") in {"organizer", "association", "event"}),
            ("Year stated", _present(facts, "year")),
            ("Dates supported", _present(facts, "start_date") or _present(facts, "dates")),
            ("Venue supported", _present(facts, "venue")),
            ("Address supported", _present(facts, "address")),
            ("Reviewed location", False),
            (
                "Possible duplicate",
                bool(item.get("duplicate_ids") or item.get("same_source_listing_ids")),
            ),
        ]
        summary = " · ".join(f"{label}: {'yes' if value else 'no'}" for label, value in flags)
        detail = "".join(
            "<p><strong>"
            + _escape(key.replace("_", " ").title())
            + ":</strong> "
            + _escape(value.get("value"))
            + "</p>"
            for key, value in facts.items()
            if value
        )
        evidence = "".join(
            "<li>" + _escape(key) + ": “" + _escape(value["evidence"]["original_quote"]) + "”</li>"
            for key, value in facts.items()
            if value and value.get("evidence")
        )
        for note in item.get("summaries", {}).get("about", []):
            detail += "<p><strong>About:</strong> " + _escape(note["text"]) + "</p>"
        for note in item.get("summaries", {}).get("programme", [])[:3]:
            detail += "<p><strong>Programme:</strong> " + _escape(note["text"]) + "</p>"
        duplicate = (
            ", ".join(item.get("duplicate_ids", []) + item.get("same_source_listing_ids", []))
            or "None found"
        )
        buttons = ""
        if item["review_state"] == "pending":
            for action, label in (
                ("current_edition_reviewed", "Approve reviewed"),
                ("source_listed", "Approve source-listed"),
                ("defer", "Defer"),
                ("reject", "Reject"),
            ):
                disabled = ""
                if action.endswith("reviewed") or action == "source_listed":
                    try:
                        compile_record(root, item, action)
                    except (ValueError, KeyError):
                        disabled = " disabled title='Required supported facts are missing'"
                buttons += f'<button name="action" value="{action}"{disabled}>{label}</button>'
        cards.append(
            f'<article><p class="eyebrow">{_escape(item["region"])} · '
            f"{_escape(item['review_state'])}</p>"
            f"<h2>{_escape(item['name'])}</h2><p>{_escape(summary)}</p>"
            f"<p><strong>Proposed:</strong> {_escape(item.get('proposed_tier'))} · "
            f"<strong>Location:</strong> {_escape(item.get('map_eligibility'))}</p>"
            f"<p><strong>Possible duplicate:</strong> {_escape(duplicate)}</p>{detail}"
            f'<p><a href="{_escape(item["source_url"])}" target="_blank" '
            'rel="noopener noreferrer">Open source ↗</a></p>'
            f"<details><summary>Show exact evidence and warnings</summary><ul>{evidence}</ul>"
            f"<p>{_escape(', '.join(item.get('warnings', [])))}</p></details>"
            '<form method="post" action="/decision">'
            f'<input type="hidden" name="token" value="{_escape(nonce)}">'
            f'<input type="hidden" name="candidate_id" value="{_escape(item["candidate_id"])}">'
            f'<input type="hidden" name="revision" value="{_escape(item["source_revision"])}">'
            f'<div class="actions">{buttons}</div></form></article>'
        )
    body = (
        "".join(cards)
        or "<p>No prepared candidates yet. Source and model failures remain pending.</p>"
    )
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Puja owner review</title><style>"
        "body{font:16px/1.55 system-ui;background:#fffaf1;color:#183d40;"
        "max-width:860px;margin:auto;padding:1.25rem}"
        "article{background:white;border:1px solid #c8dddd;border-radius:16px;"
        "padding:1.25rem;margin:1rem 0;box-shadow:0 4px 18px #183d4010}"
        "h1,h2{line-height:1.2}.eyebrow{color:#a34845;text-transform:uppercase;"
        "letter-spacing:.1em;font-size:.8rem}"
        "button{border:1px solid #367c80;background:#e8f6f5;color:#183d40;"
        "border-radius:10px;padding:.7rem;margin:.25rem;cursor:pointer}"
        "button:disabled{opacity:.45;cursor:not-allowed}"
        "button:focus-visible,a:focus-visible{outline:3px solid #b34843}"
        ".actions{display:flex;flex-wrap:wrap}details{margin:1rem 0;overflow-wrap:anywhere}"
        "li{margin:.4rem 0}</style>"
        "<main><h1>Puja owner review</h1>"
        "<p>Pending candidates stay private. Approval creates a GitHub publication request.</p>"
        f"<p role='status'>{_escape(notice)}</p>{body}</main></html>"
    )


def handler(root, nonce, submit=submit_approval):
    class ReviewHandler(BaseHTTPRequestHandler):
        def log_message(self, _format, *_args):
            pass  # Never log candidate content or request metadata.

        def _same_origin(self):
            host = f"127.0.0.1:{self.server.server_port}"
            return (
                self.headers.get("Host") == host and self.headers.get("Origin") == "http://" + host
            )

        def do_GET(self):
            if self.path not in {"/", "/index.html"} and not self.path.startswith("/?notice="):
                self.send_error(404)
                return
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.send_error(403)
                return
            notice = parse_qs(urlsplit(self.path).query).get("notice", [""])[0][:120]
            value = render(root, nonce, notice).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(value)))
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; "
                "form-action 'self'; base-uri 'none'",
            )
            self.end_headers()
            self.wfile.write(value)

        def do_POST(self):
            if self.path != "/decision" or not self._same_origin():
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    raise ValueError("invalid_request_size")
                fields = parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True)

                def one(key):
                    return fields[key][0] if len(fields[key]) == 1 else None

                if one("token") != nonce:
                    raise ValueError("invalid_review_token")
                chosen = next(
                    item for item in candidates(root) if item["candidate_id"] == one("candidate_id")
                )
                if (
                    chosen["source_revision"] != one("revision")
                    or chosen["review_state"] != "pending"
                ):
                    raise ValueError("candidate_revision_changed")
                action = one("action")
                if action in {"source_listed", "current_edition_reviewed"}:
                    payload = compile_record(root, chosen, action)
                    issue = submit(payload)
                    save_decision(root, chosen, "approved", issue_number=issue, tier=action)
                    notice = f"Approved and queued in GitHub issue {issue}."
                elif action in {"defer", "reject"}:
                    save_decision(root, chosen, action)
                    notice = action.capitalize() + "."
                else:
                    raise ValueError("invalid_review_action")
                self.send_response(303)
                self.send_header("Location", "/?notice=" + notice.replace(" ", "%20"))
                self.end_headers()
            except (KeyError, StopIteration, ValueError, RuntimeError) as exc:
                self.send_error(422, type(exc).__name__)

    return ReviewHandler


def serve(root, port=0, open_browser=True, submit=submit_approval):
    nonce = secrets.token_urlsafe(24)
    server = ThreadingHTTPServer(("127.0.0.1", port), handler(root, nonce, submit))
    url = f"http://127.0.0.1:{server.server_port}/"
    print("Puja owner review: " + url)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
