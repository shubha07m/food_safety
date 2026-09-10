import argparse
import hashlib
import json
from pathlib import Path

from .build import build, validate
from .config import ROOT
from .pipeline import review_record, update
from .storage import now, read_events, read_rejected, transaction, transition


def bounded(value):
    number = int(value)
    if not 1 <= number <= 30:
        raise argparse.ArgumentTypeError("must be between 1 and 30")
    return number


def main():
    parser = argparse.ArgumentParser(description="Independent public-source evidence tracker")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["validate", "build", "pending", "migrate"]:
        sub.add_parser(name)
    scan = sub.add_parser("update")
    scan.add_argument("--max-articles", type=bounded, default=3)
    scan.add_argument("--max-llm-calls", type=int, default=None)
    llm = scan.add_mutually_exclusive_group()
    llm.add_argument("--use-llm", dest="use_llm", action="store_true")
    llm.add_argument("--no-llm", dest="use_llm", action="store_false")
    scan.set_defaults(use_llm=None)
    corpus = sub.add_parser(
        "llm-prepare", help="Fetch bounded known articles into private evaluation"
    )
    corpus.add_argument("--max-articles", type=bounded, default=30)
    evaluation = sub.add_parser(
        "llm-evaluate", help="Evaluate frozen private articles; no source fetch"
    )
    evaluation.add_argument("--max-articles", type=bounded, default=30)
    evaluation.add_argument("--use-llm", action="store_true", help="Permit bounded model calls")
    review = sub.add_parser("review", help="Publish a reviewed record after fresh source checks")
    review.add_argument("--file", required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--note", required=True)
    review.add_argument("--attest-source-context", action="store_true", required=True)
    review.add_argument("--attest-all-fields", action="store_true", required=True)
    review.add_argument(
        "--cross-source",
        action="store_true",
        help="Requires reviewed independent field-level associations",
    )
    hold = sub.add_parser("hold", help="Suspend a record immediately; retain private history")
    hold.add_argument("event_id")
    hold.add_argument(
        "--status",
        choices=["DISPUTED", "SOURCE WITHDRAWN", "SUPERSEDED", "PENDING REVIEW", "REJECTED"],
        default="DISPUTED",
    )
    hold.add_argument("--note", required=True)
    hold.add_argument("--replacement-id", help="Required for SUPERSEDED; must already be active")
    args = parser.parse_args()
    try:
        if args.command in {"llm-prepare", "llm-evaluate"}:
            from .evaluation import evaluate_corpus, prepare_corpus

            result = (
                prepare_corpus(ROOT, args.max_articles)
                if args.command == "llm-prepare"
                else evaluate_corpus(ROOT, args.max_articles, args.use_llm)
            )
        elif args.command == "migrate":
            from .migrate import migrate

            migrate(ROOT)
            result = {"migration": "complete"}
        elif args.command == "validate":
            result = validate(ROOT)
        elif args.command == "build":
            result = build(ROOT)
        elif args.command == "pending":
            result = [
                {
                    "event_id": e.event_id,
                    "status": e.verification_status,
                    "note": e.verification_notes,
                }
                for e in read_events(ROOT, "pending")
            ]
        elif args.command == "update":
            result = update(ROOT, args.max_articles, args.use_llm, args.max_llm_calls)
            build(ROOT)
        elif args.command == "review":
            path = Path(args.file).resolve()
            if not path.is_relative_to(ROOT):
                raise ValueError("review_file_must_be_inside_project")
            result = review_record(
                ROOT,
                json.loads(path.read_text()),
                args.reviewer,
                args.note,
                cross_source=args.cross_source,
            )
            build(ROOT)
        else:
            at = now()
            events, pending = read_events(ROOT, "events"), read_events(ROOT, "pending")
            old = next((e for e in [*events, *pending] if e.event_id == args.event_id), None)
            if old is None:
                raise ValueError("unknown_event_id")
            revised = transition(ROOT, old, args.status, args.note, at)
            if args.status == "SUPERSEDED":
                if not any(
                    e.event_id == args.replacement_id and e.event_id != old.event_id for e in events
                ):
                    raise ValueError("superseded_requires_active_replacement")
                revised.superseded_by = args.replacement_id
            events = [e for e in events if e.event_id != old.event_id]
            pending = [e for e in pending if e.event_id != old.event_id] + [revised]
            rejected = read_rejected(ROOT)["records"]
            if args.status == "REJECTED":
                rejected.append(
                    {
                        "candidate_id": hashlib.sha256(old.event_id.encode()).hexdigest()[:16],
                        "at": at.isoformat(),
                        "reason": "maintainer_rejected",
                    }
                )
            transaction(ROOT, events, pending, rejected, at)
            build(ROOT)
            result = {"event_id": old.event_id, "status": args.status}
        print(json.dumps(result, indent=2))
        if args.command == "update" and result["errors"]:
            parser.exit(2, "Source scan incomplete; last successful update has not advanced.\n")
    except Exception as exc:
        # Validation errors can contain input values; never echo raw exception text.
        parser.exit(1, f"Command failed ({type(exc).__name__}); inspect local inputs and tests.\n")


if __name__ == "__main__":
    main()
