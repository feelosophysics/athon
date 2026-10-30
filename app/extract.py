"""대화 구간에서 개념을 고르고, 말에 나온 값과 상황을 시작 상태로 옮긴다."""

import re

from pydantic import BaseModel

from . import llm
from .concepts import CONCEPTS, concept_list_for_prompt, keyword_score
from .numbers import normalize_numbers
from .states import HashState, LruOp, LruState, parse_state


class Analysis(BaseModel):
    scores: dict[str, float]  # 개념 id → 지금 대화와 맞는 정도(0~1)
    states: dict[str, dict]  # 시각화가 있는 개념 id → 대화에서 뽑은 시작 상태
    latest: list[str] = []  # 가장 최근 발화에서 말한 개념
    source: str  # "llm" 또는 "rules"


SYSTEM_PROMPT = """너는 컴퓨터공학 동료 평가 대화를 듣고, 지금 이야기하는 개념을 고르는 도우미다.
후보 개념 목록에 있는 id만 쓴다. 대화와 관계없는 개념은 넣지 않는다.

후보 개념:
{concepts}

대화에 예시 값이 나오면 시각화 시작 상태로 옮긴다.
- hash_chaining: {{"size": 칸 수(기본 10), "keys": [정수 키], "focus": "insert"|"collision"|"lookup"|"long_chain", "lookup": 찾는 키 또는 null}}
- lru: {{"capacity": 용량(기본 3), "ops": [{{"op": "put"|"get", "key": "A"}}], "stop_at": 멈출 연산 번호 또는 null}}
말에 값이 없으면 그 개념의 상태는 넣지 않는다. 값을 지어내지 않는다.
발화는 시간 순서이고 마지막 줄이 가장 최근이다. 최근에 말한 개념일수록 점수를 높게 준다.
값은 그 개념을 말한 발화와, 그 뒤에 이어지는 후속 발화에서만 가져온다. 다른 개념을 말한 발화의 숫자는 섞지 않는다.

다음 JSON만 출력한다:
{{"scores": {{"개념 id": 0~1}}, "states": {{"개념 id": 시작 상태}}, "latest": [마지막 발화에서 말한 개념 id]}}"""


def analyze(lines: list[str]) -> Analysis:
    talk = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines))
    raw = llm.complete_json(SYSTEM_PROMPT.format(concepts=concept_list_for_prompt()), talk)
    if raw is not None:
        result = _from_llm(raw)
        if result is not None:
            return result
    return analyze_with_rules(lines)


def _from_llm(raw: dict) -> Analysis | None:
    scores = {k: float(v) for k, v in (raw.get("scores") or {}).items() if k in CONCEPTS and _is_number(v)}
    states = {}
    for cid, state in (raw.get("states") or {}).items():
        concept = CONCEPTS.get(cid)
        parsed = parse_state(concept.viz, state) if concept and concept.viz else None
        if parsed is not None:
            states[cid] = parsed.model_dump()
    if not scores:
        return None
    scores = {k: max(0.0, min(1.0, v)) for k, v in scores.items()}
    latest = [k for k in raw.get("latest") or [] if k in scores]
    return Analysis(scores=scores, states=states, latest=latest, source="llm")


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# ---- 규칙 기반 경로: LLM 서버가 없을 때와 LLM 응답이 형식에 맞지 않을 때 쓴다 ----

RECENCY = 0.85  # 한 발화 전으로 갈 때마다 점수에 곱한다
# 함수는 아래에서 정의되므로 이름으로 늦게 찾는다
STATE_FROM_TEXT = {"hash_chaining": lambda t: hash_state_from_text(t), "lru": lambda t: lru_state_from_text(t)}


def analyze_with_rules(lines: list[str] | str) -> Analysis:
    if isinstance(lines, str):
        lines = [lines]
    per_line = [
        {c.id: s for c in CONCEPTS.values() if (s := keyword_score(c, line.lower())) > 0} for line in lines
    ]
    scores: dict[str, float] = {}
    for age, line_scores in enumerate(reversed(per_line)):
        for cid, s in line_scores.items():
            scores[cid] = max(scores.get(cid, 0.0), round(s * RECENCY**age, 3))
    states = {}
    for cid, extract in STATE_FROM_TEXT.items():
        if cid not in scores:
            continue
        # 가장 최근에 말한 곳부터 거슬러 올라가며 값이 있는 곳을 찾는다.
        # "LRU는 해시맵으로"처럼 값 없이 이름만 나온 발화 때문에 앞에서 말한 값을 잃지 않게 한다
        for start in reversed([i for i, s in enumerate(per_line) if cid in s]):
            if (s := extract(_talk_from(start, lines, per_line))) is not None:
                states[cid] = s.model_dump()
                break
    return Analysis(scores=scores, states=states, latest=list(per_line[-1]) if per_line else [], source="rules")


def _talk_from(start: int, lines: list[str], per_line: list[dict]) -> str:
    """그 개념을 말한 발화와, 다른 개념이 나오기 전까지의 후속 발화를 잇는다."""
    end = start + 1
    while end < len(lines) and not per_line[end]:
        end += 1
    return " ".join(lines[start:end])


def _spans(patterns: list[re.Pattern], text: str) -> tuple[int | None, list[tuple[int, int]]]:
    """크기·용량을 말한 부분을 찾는다. 마지막으로 말한 값과, 키에서 뺄 위치를 돌려준다."""
    value, spans = None, []
    for p in patterns:
        for m in p.finditer(text):
            value = int(m.group(1))
            spans.append(m.span())
    return value, spans


def _outside(pos: int, spans: list[tuple[int, int]]) -> bool:
    return not any(a <= pos < b for a, b in spans)


HASH_SIZE_PATTERNS = [
    re.compile(r"(?:크기|칸\s*수|버킷\s*수|사이즈|size)\s*(?:가|는|를|이|은)?\s*(\d+)", re.IGNORECASE),
    re.compile(r"(?:버킷|칸|슬롯)\s*(?:이|가|은|는)?\s*(\d+)\s*개"),
    re.compile(r"(\d+)\s*칸\s*(?:짜리|인|으로)"),
]
NUMBER_PATTERN = re.compile(r"\d+")
LOOKUP_PATTERN = re.compile(r"(\d+)\s*(?:을|를|은|는|이|가)?\s*(?:다시\s*)?(?:찾|조회|검색)")


def hash_state_from_text(text: str) -> HashState | None:
    text = normalize_numbers(text)
    size, size_spans = _spans(HASH_SIZE_PATTERNS, text)
    lookup_match = LOOKUP_PATTERN.search(text)
    skip = size_spans + ([lookup_match.span(1)] if lookup_match else [])
    keys = [int(m.group()) for m in NUMBER_PATTERN.finditer(text) if _outside(m.start(), skip)]
    if not keys:
        return None
    focus = "insert"
    lookup = None
    if re.search(r"같은\s*칸|충돌|겹", text):
        focus = "collision"
    if lookup_match:
        focus = "lookup"
        lookup = int(lookup_match.group(1))
    try:
        return HashState(size=max(2, min(size or 10, 16)), keys=keys[:16], focus=focus, lookup=lookup)
    except ValueError:
        return None


LRU_CAPACITY_PATTERNS = [
    re.compile(r"(?:용량|크기|capacity)\s*(?:이|가|는|은)?\s*(\d+)", re.IGNORECASE),
    re.compile(r"(\d+)\s*개\s*(?:까지|짜리)"),
]
# STT가 영문 키를 한글 이름으로 적은 경우
LETTER_NAMES = {"에이": "A", "비": "B", "씨": "C", "디": "D", "에프": "F"}
LETTER_NAME_PATTERN = re.compile(
    r"(?<![가-힣])(" + "|".join(LETTER_NAMES) + r")(?=(?:를|을|가|이|는|은|랑|와|과|하고|도|만)?(?![가-힣]))"
)
# "A를"처럼 한글 조사가 바로 붙으므로 \b 대신 영문자 경계만 본다
LETTER_KEY_PATTERN = re.compile(r"(?<![A-Za-z])([A-Za-z])(?![A-Za-z])")
NUMBER_KEY_PATTERN = re.compile(r"(?<!\d)(\d{1,3})(?!\d)")
GET_AFTER_KEY = re.compile(r"^\s*(?:를|을|만|은|는)?\s*(?:다시\s*)?(?:조회|읽|접근|get|사용|쓰|꺼내)", re.IGNORECASE)
# "B가 빠지지?"처럼 결과를 묻는 말은 연산이 아니다
EVICT_AFTER_KEY = re.compile(r"^\s*(?:가|이|는|은)?\s*(?:빠|나가|밀려|쫓겨|축출|evict)", re.IGNORECASE)


def lru_state_from_text(text: str) -> LruState | None:
    text = LETTER_NAME_PATTERN.sub(lambda m: LETTER_NAMES[m.group(1)], normalize_numbers(text))
    capacity, capacity_spans = _spans(LRU_CAPACITY_PATTERNS, text)
    matches = list(LETTER_KEY_PATTERN.finditer(text))
    if not matches:
        matches = [m for m in NUMBER_KEY_PATTERN.finditer(text) if _outside(m.start(), capacity_spans)]
    ops = []
    seen = set()
    for m in matches:
        key = m.group(1).upper()
        rest = text[m.end() :]
        if EVICT_AFTER_KEY.match(rest):
            continue
        is_get = key in seen and GET_AFTER_KEY.match(rest) is not None
        ops.append(LruOp(op="get" if is_get else "put", key=key))
        seen.add(key)
    if not ops:
        return None
    try:
        return LruState(capacity=max(2, min(capacity or 3, 6)), ops=ops[:16])
    except ValueError:
        return None
