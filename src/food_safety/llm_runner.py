"""Bounded LLM extraction side path. It never changes source lifecycle state."""

import hashlib
import json
import os
import time
from collections import Counter

from .candidates import TASK_VERSION, parse_result, schema, validate_candidate
from .documents import freeze_document
from .storage import dump, now
from .structured_llm import PROMPT, GeminiExtractor, ModelFailure


class LLMRunner:
    def __init__(self, root, cfg, enabled=None, max_calls=None, extractor=None):
        self.root, self.cfg = root, cfg
        configured = os.getenv("LLM_ENABLED", str(cfg.llm_enabled)).lower() == "true"
        self.enabled = configured if enabled is None else configured and enabled
        self.extractor = extractor or GeminiExtractor(cfg.llm_model)
        self.max_calls = min(cfg.max_llm_calls_per_run, max_calls if max_calls is not None else 5)
        self.calls = 0
        self.counts = Counter()

    def observe(self, html, url, language, deterministic=()):
        return self.observe_document(lambda: freeze_document(html, url, language), deterministic)

    def observe_document(self, document, deterministic=()):
        """Accept a frozen revision (or lazy parser) for repeatable offline evaluations."""
        # All failures are contained here, including private disk/cache failures.
        try:
            result = self._observe(document, deterministic)
        except ModelFailure as exc:
            result = {"status": exc.code, "publication_eligible": False}
            if exc.diagnostic:
                result["provider_diagnostic"] = exc.diagnostic
        except Exception:
            result = {
                "status": "llm_processing_failure",
                "publication_eligible": False,
            }
        self.counts[result["status"]] += 1
        return result

    def _observe(self, document, deterministic):
        if not self.enabled:
            return {"status": "disabled"}
        if not getattr(self.extractor, "available", True):
            return {"status": "missing_credentials"}
        document = document() if callable(document) else document
        candidate_schema = schema()
        input_chars = sum(len(p.original_text) for p in document.passages)
        if input_chars > self.cfg.llm_max_input_chars:
            return {"status": "input_incomplete", "input_chars": input_chars}
        schema_hash = hashlib.sha256(
            json.dumps(candidate_schema, sort_keys=True).encode(),
        ).hexdigest()
        identity = {
            "source_id": document.source_id,
            "source_revision_id": document.source_revision_id,
            "source_language": document.source_language,
            "parser_version": document.parser_version,
            "schema_hash": schema_hash,
            "validator_id": "field_grounding_and_explicit_relationships",
            "validator_version": "1",
            "task_version": TASK_VERSION,
            "prompt_hash": hashlib.sha256(PROMPT.encode()).hexdigest(),
            "provider": self.cfg.llm_provider,
            "model": self.cfg.llm_model,
            "output_limit": self.cfg.llm_max_output_tokens,
            "candidate_limit": self.cfg.llm_max_candidates,
        }
        cache_key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        private = self.root / ".cache/llm"
        path = private / "responses" / f"{cache_key}.json"
        cached = json.loads(path.read_text()) if path.exists() else None
        cached_at = cached.get("at") if cached else None
        latency = 0.0
        if cached:
            payload, usage = cached["response"], cached["usage"]
        else:
            if self.calls >= self.max_calls:
                raise ModelFailure("call_budget_exhausted")
            self.calls += 1
            started = time.monotonic()
            reply = self.extractor.extract(document, candidate_schema, TASK_VERSION, self.cfg)
            latency = time.monotonic() - started
            payload = reply.text
            if len(payload.encode()) > 131072:
                raise ModelFailure("response_too_large")
            usage = {
                "input_tokens": reply.input_tokens,
                "output_tokens": reply.output_tokens,
                "model_version": reply.model_version,
                "estimated_list_cost_usd": (
                    reply.input_tokens * self.cfg.llm_input_usd_per_million
                    + reply.output_tokens * self.cfg.llm_output_usd_per_million
                )
                / 1e6,
            }
        status, candidates, invalid = parse_result(payload, self.cfg.llm_max_candidates)
        if status == "incomplete":
            raise ModelFailure("incomplete_response")
        results, seen = [], set()
        for candidate in candidates:
            result = validate_candidate(candidate, document, deterministic)
            if result["candidate_key"] in seen:
                continue
            seen.add(result["candidate_key"])
            results.append(result)
        at = now().isoformat()
        report = {
            **identity,
            "at": at,
            "completion_status": status,
            "status": "evaluated",
            "publication_eligible": self.cfg.publish_from_llm,
            "usage": usage,
            "estimated_current_call_cost_usd": 0 if cached else usage["estimated_list_cost_usd"],
            "latency_seconds": latency,
            "cache_hit": cached is not None,
            "model_called_at": cached_at or at,
            "invalid_candidates": invalid,
            "candidates": results,
        }
        if not cached:
            dump(path, {"at": at, "response": payload, "usage": usage})
        dump(private / "results" / f"{cache_key}.json", report)
        return report
