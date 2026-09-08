"""Two configured discovery-page diagnostics, no ingestion or stored article bodies."""

from food_safety.automatic import page_candidates
from food_safety.config import ROOT, settings, sources
from food_safety.fetch import Fetcher, FetchError


def main():
    policies = sources(ROOT)
    cfg = settings(ROOT)
    fetcher = Fetcher(
        policies, cfg.model_copy(update={"max_response_bytes": cfg.max_discovery_response_bytes})
    )
    checks = [(p, u) for p in policies if p.enabled for u in p.discovery_pages][:2]
    for policy, url in checks:
        try:
            _, body = fetcher.article(url)
            print(
                policy.name,
                {
                    "candidates": len(page_candidates(body, policy, 6)),
                    "response_bytes": len(body.encode()),
                },
            )
        except FetchError as exc:
            print(policy.name, "fetch_policy_result:", str(exc))
        except Exception as exc:
            print(policy.name, "error_type:", type(exc).__name__)


if __name__ == "__main__":
    main()
