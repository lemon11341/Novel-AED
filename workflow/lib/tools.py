"""Deterministic tools. No shell or arbitrary code execution is exposed to models."""


def chunk_text(text, size=10000):
    """Preserve exact text and offsets, including whitespace; no input is dropped."""
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + size // 2, end)
            if boundary >= 0:
                end = boundary + 1
        chunks.append({"id": f"src-{len(chunks)+1:04d}", "start": start,
                       "end": end, "text": text[start:end]})
        start = end
    return chunks


def ground_claims(analysis, chunks):
    """Verify quote existence and attach exact offsets. Reject invented citations."""
    by_id = {c["id"]: c for c in chunks}
    for claim in analysis["claims"]:
        for ev in claim["evidence"]:
            chunk = by_id.get(ev["chunk_id"])
            at = chunk["text"].find(ev["quote"]) if chunk else -1
            if at < 0:
                raise ValueError("원문에 없는 근거 인용입니다. 분석 결과를 승인할 수 없습니다.")
            ev["start"] = chunk["start"] + at
            ev["end"] = ev["start"] + len(ev["quote"])
    return analysis

