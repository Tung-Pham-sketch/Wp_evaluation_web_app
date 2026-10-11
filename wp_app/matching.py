from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping


AUTO_MATCH = "AUTO_MATCH"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
NOT_FOUND = "NOT_FOUND"
NOT_APPLICABLE = "NOT_APPLICABLE"

PREFIX_MIN_CHARS = 4
PREFIX_REVIEW_THRESHOLD = 60.0
TITLE_REVIEW_THRESHOLD = 65.0


def normalize(value: Any) -> str:
    """Normalize identifiers without changing their business punctuation."""
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


def taskcard_core(value: Any) -> str:
    """Return an MPD/taskcard key without its trailing slash revision."""
    return re.sub(r"/\d{2}$", "", normalize(value))


def common_prefix_length(left: Any, right: Any) -> int:
    left_text = normalize(left).replace(" ", "")
    right_text = normalize(right).replace(" ", "")
    count = 0
    for left_char, right_char in zip(left_text, right_text):
        if left_char != right_char:
            break
        count += 1
    return count


def prefix_similarity(left: Any, right: Any) -> float:
    left_text = normalize(left).replace(" ", "")
    right_text = normalize(right).replace(" ", "")
    if not left_text or not right_text:
        return 0.0
    return round(100 * common_prefix_length(left_text, right_text) / max(len(left_text), len(right_text)), 1)


def normalize_title(value: Any) -> str:
    text = normalize(value)
    text = re.sub(r"^\(\d+\)\s*", "", text)
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def title_similarity(left: Any, right: Any) -> float:
    left_text = normalize_title(left)
    right_text = normalize_title(right)
    if not left_text or not right_text:
        return 0.0
    character_score = SequenceMatcher(None, left_text, right_text).ratio()
    stop_words = {"A", "AN", "AND", "FOR", "FROM", "IN", "OF", "ON", "THE", "TO", "WITH"}
    left_tokens = {token for token in left_text.split() if token not in stop_words}
    right_tokens = {token for token in right_text.split() if token not in stop_words}
    token_score = 0.0
    if left_tokens and right_tokens:
        token_score = 2 * len(left_tokens & right_tokens) / (len(left_tokens) + len(right_tokens))
    return round(100 * max(character_score, token_score), 1)


def canonical_customer(value: Any) -> str:
    text = normalize(value)
    if text in {"VA-VJ", "VJC", "VIETJET", "VIETJET AIR"}:
        return "VA-VJ"
    if text in {"DLH", "LUFTHANSA", "LUFTHANSA GERMAN AIRLINES"}:
        return "DLH"
    return text


def canonical_aircraft(value: Any) -> str:
    text = normalize(value).replace("AIRBUS", "").replace("BOEING", "").strip()
    compact = re.sub(r"[\s_-]+", "", text)
    aliases = {
        "320": "A320", "A320": "A320", "321": "A321", "A321": "A321",
        "32S": "A32S", "A32S": "A32S", "A320/A321": "A32S",
        "350": "A350", "A350": "A350", "787": "B787", "B787": "B787",
        "ATR": "ATR", "ATR72": "ATR",
    }
    return aliases.get(compact, compact)


def aircraft_from_amp_name(amp_name: Any, fallback: Any = None) -> str:
    """Derive the real model from VNA AMP Name; A/C Type is often only 32S."""
    text = normalize(amp_name)
    found = {f"A{model}" for model in re.findall(r"A?(320|321|350)\b", text)}
    found.update({f"B{model}" for model in re.findall(r"B?(787)\b", text)})
    if {"A320", "A321"}.issubset(found):
        return "A32S"
    if len(found) == 1:
        return next(iter(found))
    return canonical_aircraft(fallback)


def aircraft_rank(candidate: Any, requested: Any) -> int | None:
    """Rank exact model before family; never cross-match A320 with A321."""
    candidate_model = canonical_aircraft(candidate)
    requested_model = canonical_aircraft(requested)
    if not requested_model:
        return 0
    if candidate_model == requested_model:
        return 0
    if requested_model in {"A320", "A321"} and candidate_model == "A32S":
        return 1
    if requested_model == "A32S" and candidate_model in {"A320", "A321"}:
        return 1
    return None


def parse_mhr(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if ":" in text:
        try:
            hours, minutes = text.split(":", 1)
            return round(float(hours) + float(minutes) / 60, 2)
        except ValueError:
            return None
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def is_match_eligible(adapter: Any, event_type: Any) -> bool:
    """Limit MPD matching to the approved taskcard block for each adapter."""
    adapter_key = normalize(adapter)
    if adapter_key == "VIETJET":
        return normalize(event_type) == "BLOCK TASKCARD"
    if adapter_key in {"LUFTHANSA", "DLH"}:
        return normalize(event_type) == "MS ITEM"
    return False


def _as_dict(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in record.keys()}


def _join_unique(records: list[dict[str, Any]], field: str) -> Any:
    values: list[str] = []
    for record in records:
        value = record.get(field)
        if value is None or str(value).strip() == "":
            continue
        text = str(value).strip()
        if normalize(text) not in {normalize(item) for item in values}:
            values.append(text)
    return "; ".join(values) if values else None


@dataclass(frozen=True)
class CandidateResolution:
    status: str
    record: dict[str, Any] | None
    candidate_count: int
    note: str | None = None


@dataclass(frozen=True)
class MatchDecision:
    status: str
    method: str
    record: dict[str, Any] | None
    candidate_count: int
    note: str | None = None
    score: float | None = None
    layer: int | None = None


@dataclass(frozen=True)
class ScoredCandidate:
    record: dict[str, Any]
    score: float
    candidate_count: int
    tied_count: int


def resolve_candidates(records: Iterable[Mapping[str, Any]], requested_aircraft: Any) -> CandidateResolution:
    """Select the best aircraft scope and collapse repeated item-level rows."""
    ranked: list[tuple[int, dict[str, Any]]] = []
    for raw in records:
        record = _as_dict(raw)
        rank = aircraft_rank(record.get("aircraft_model") or record.get("aircraft_type"), requested_aircraft)
        if rank is not None:
            ranked.append((rank, record))
    if not ranked:
        return CandidateResolution(NOT_FOUND, None, 0)
    best_rank = min(rank for rank, _ in ranked)
    candidates = [record for rank, record in ranked if rank == best_rank]
    signatures = {
        (normalize(record.get("title")), parse_mhr(record.get("planning_mhr")))
        for record in candidates
    }
    if len(signatures) > 1:
        return CandidateResolution(
            REVIEW_REQUIRED, dict(candidates[0]), len(candidates),
            "Có nhiều candidate cùng mức ưu tiên nhưng khác Taskcard Title hoặc Planning MHR.",
        )
    merged = dict(candidates[0])
    for field in (
        "zone", "area", "panel", "special_code", "resource_type", "classification",
        "type_code", "qualification", "information_skill", "requirement_link",
        "linked_jobcards", "jobcards_title",
    ):
        merged[field] = _join_unique(candidates, field)
    return CandidateResolution(AUTO_MATCH, merged, len(candidates))


def best_scored_candidate(records: Iterable[Mapping[str, Any]], requested_aircraft: Any,
                          target: Any, *, kind: str, threshold: float) -> ScoredCandidate | None:
    """Return the best distinct compatible taskcard above a review threshold."""
    candidates: dict[str, tuple[float, int, dict[str, Any]]] = {}
    for raw in records:
        record = _as_dict(raw)
        rank = aircraft_rank(record.get("aircraft_model") or record.get("aircraft_type"), requested_aircraft)
        if rank is None:
            continue
        if kind == "prefix":
            candidate_value = record.get("taskcard_core_key") or record.get("taskcard_key") or record.get("task_no")
            if common_prefix_length(target, candidate_value) < PREFIX_MIN_CHARS:
                continue
            score = prefix_similarity(target, candidate_value)
        elif kind == "title":
            score = title_similarity(target, record.get("title"))
        else:
            raise ValueError(f"Unknown candidate scoring kind: {kind}")
        if score < threshold:
            continue
        identity = normalize(
            record.get("taskcard_key") or record.get("taskcard_core_key")
            or record.get("task_no") or record.get("id")
        )
        previous = candidates.get(identity)
        if previous is None or score > previous[0] or (score == previous[0] and rank < previous[1]):
            candidates[identity] = (score, rank, record)
    if not candidates:
        return None
    ordered = sorted(candidates.values(), key=lambda item: (-item[0], item[1], item[2].get("id") or 0))
    best_score, _, best_record = ordered[0]
    tied_count = sum(1 for score, _, _ in ordered if score == best_score)
    return ScoredCandidate(best_record, best_score, len(ordered), tied_count)
