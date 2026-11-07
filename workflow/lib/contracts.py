"""Shared structured output contracts and strict local validation."""
import math


def obj(**properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def arr(items, **kwargs):
    return {"type": "array", "items": items, "maxItems": 64, **kwargs}


def string(**kwargs):
    return {"type": "string", "minLength": 1, "maxLength": 2000, **kwargs}


CATEGORIES = ["character", "event", "world", "narration", "style", "theme", "thread", "emotion"]
EVIDENCE = obj(chunk_id=string(), quote=string(maxLength=400))
CLAIM = obj(category=string(enum=CATEGORIES), subject=string(), statement=string(),
            epistemic=string(enum=["explicit", "inferred", "hypothesis"]),
            confidence={"type": "number", "minimum": 0, "maximum": 1},
            evidence=arr(EVIDENCE, minItems=1, maxItems=4))
ANALYSIS = obj(summary=string(), claims=arr(CLAIM, minItems=1, maxItems=48),
               unknowns=arr(string()), structure_notes=arr(string()))
NARRATIVE_ASSESSMENT = obj(
    progress=string(), open_arcs=arr(string()), pacing_baseline=string(), recent_pacing=string(),
    continuation_strategy=string(), ending_allocation=string(),
    evidence=arr(EVIDENCE, minItems=1, maxItems=8), uncertainties=arr(string()))
PACING = obj(pace=string(), event_density=string(), story_time=string(),
             scene_balance=string(), tension=string(), transition=string())
CHAPTER = obj(number={"type": "integer", "minimum": 1}, title=string(),
              goal=string(), beats=arr(string(), minItems=2, maxItems=8),
              canon_ids=arr(string(), minItems=1), thread_ids=arr(string()),
              ending=string(), pacing=PACING)
PLAN = obj(premise=string(), ending=string(), chapters={"type": "array", "items": CHAPTER, "minItems": 1},
           unresolved=arr(string()), narrative_assessment=NARRATIVE_ASSESSMENT)
DRAFT = obj(title=string(), text=string(minLength=100, maxLength=30000),
            state_changes=arr(string(maxLength=500),maxItems=24), resolved_thread_ids=arr(string(maxLength=64),maxItems=24))
ISSUE = obj(severity=string(enum=["high", "medium", "low"]),
            category=string(enum=["canon", "timeline", "knowledge", "character", "style", "outline", "thread", "pacing", "reference"]),
            description=string(), draft_quote=string(), canon_ids=arr(string()))
REVIEW = obj(verdict=string(enum=["pass", "revise"]), issues=arr(ISSUE),
             rationale=string())
ANALYSIS_SUBMISSION = obj(parts={"type": "array", "items": ANALYSIS, "minItems": 1})
CHAPTER_SUBMISSION = obj(draft=DRAFT, review=REVIEW)


def validate(value, schema, path="result"):
    kind = schema["type"]
    ok = {"object": lambda: isinstance(value, dict),
          "array": lambda: isinstance(value, list),
          "string": lambda: isinstance(value, str),
          "number": lambda: type(value) in (int, float) and math.isfinite(value),
          "integer": lambda: type(value) is int}[kind]()
    if not ok:
        raise ValueError(f"{path}: {kind} 형식이 필요합니다.")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: 허용되지 않은 값입니다.")
    if kind == "object":
        if set(value) != set(schema["properties"]):
            raise ValueError(f"{path}: 필수 필드 또는 알 수 없는 필드를 확인하세요.")
        for key, child in schema["properties"].items():
            validate(value[key], child, f"{path}.{key}")
    if kind in ("array", "string"):
        minimum = schema.get("minItems" if kind == "array" else "minLength", 0)
        maximum = schema.get("maxItems" if kind == "array" else "maxLength", float("inf"))
        if not minimum <= len(value) <= maximum or (kind == "string" and not value.strip()):
            raise ValueError(f"{path}: 길이가 올바르지 않습니다.")
        if kind == "array":
            for i, child in enumerate(value):
                validate(child, schema["items"], f"{path}[{i}]")
    if kind in ("number", "integer"):
        if not schema.get("minimum", -float("inf")) <= value <= schema.get("maximum", float("inf")):
            raise ValueError(f"{path}: 허용 범위를 벗어났습니다.")
    return value


LENGTH_SPEC = obj(chapters_count={"type": "integer", "minimum": 1},
                  target_chars={"type": "integer", "minimum": 100, "maximum": 12000}, rationale=string())


def plan_schema(params):
    import copy
    result = copy.deepcopy(PLAN)
    if params.get("length_mode"):
        result["properties"]["length_spec"] = LENGTH_SPEC
        result["required"].append("length_spec")
    return result
