"""Shared artifact checks, independent of model, transport, and execution mode."""
import hashlib
import json

from . import contracts as c
from .tools import ground_claims


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def analyze_chunk(payload, chunk):
    c.validate(payload, c.ANALYSIS)
    return ground_claims(payload, [chunk])


def bible(parts, project):
    claims, summaries, unknowns, notes = [], [], [], []
    for chunk, part in zip(project["chunks"], parts):
        summaries.append({"chunk_id": chunk["id"], "summary": part["summary"]})
        for claim in part["claims"]:
            claims.append({**claim, "id": f"canon-{len(claims)+1:05d}"})
        unknowns.extend(part["unknowns"])
        notes.extend(part["structure_notes"])
    result = {"summaries": summaries, "claims": claims, "unknowns": unknowns, "structure_notes": notes,
              "method": "research-informed-llm-v2", "source_characters": len(project["source"])}
    if len(json.dumps(result, ensure_ascii=False)) > 350000:
        raise ValueError("분석 결과가 집필 크기 한도를 넘었습니다. 원문을 나눠 등록하세요.")
    return result


class LengthMismatch(ValueError):
    pass


def plan(payload, project, count, params=None):
    params = params or {}
    c.validate(payload, c.plan_schema(params))
    if params.get("length_mode"):
        spec = payload["length_spec"]
        if spec["chapters_count"] != len(payload["chapters"]):
            raise ValueError("Length specification and chapter count differ.")
        if params["length_mode"] == "custom" and spec["target_chars"] != params["target_chars"]:
            raise ValueError("The plan must use the specified character count.")
    # Reuse the source-quote check without adding analysis-only offsets to the plan contract.
    ground_claims({"claims": [{"evidence": [dict(ev) for ev in payload["narrative_assessment"]["evidence"]]}]}, project["chunks"])
    if params.get("count_mode", "custom") == "custom" and len(payload["chapters"]) != count:
        raise ValueError("요청한 회차 수와 개요가 일치하지 않습니다.")
    canon = {claim["id"] for claim in project["bible"]["claims"]}
    threads = {claim["id"] for claim in project["bible"]["claims"] if claim["category"] == "thread"}
    for i, chapter in enumerate(payload["chapters"], 1):
        if chapter["number"] != i or not set(chapter["canon_ids"]) <= canon or not set(chapter["thread_ids"]) <= threads:
            raise ValueError("개요에 존재하지 않는 설정·복선 참조 또는 잘못된 회차 번호가 있습니다.")
    return payload


def draft(payload, project):
    c.validate(payload, c.DRAFT)
    spec = project["plan"].get("length_spec")
    actual = sum(not ch.isspace() for ch in payload["text"])
    if spec and actual != spec["target_chars"]:
        raise LengthMismatch(f"Chapter body has {actual} non-whitespace characters; exactly {spec['target_chars']} required. Revise naturally, recount and resubmit. Title is excluded.")
    threads = {claim["id"] for claim in project["bible"]["claims"] if claim["category"] == "thread"}
    if not set(payload["resolved_thread_ids"]) <= threads:
        raise ValueError("초안에 존재하지 않는 복선 ID가 있습니다.")
    return payload


def review(payload, project, saved_draft):
    c.validate(payload, c.REVIEW)
    canon = {claim["id"] for claim in project["bible"]["claims"]}
    for issue in payload["issues"]:
        if issue["draft_quote"] not in saved_draft["text"] or not set(issue["canon_ids"]) <= canon:
            raise ValueError("검토 결과의 인용 또는 설정 참조가 잘못되었습니다.")
    if any(issue["severity"] in ("high", "medium") for issue in payload["issues"]):
        payload["verdict"] = "revise"
    return payload
