"""대화 분석 결과와 피평가자의 개념별 상태로 추천 카드를 만든다.

순위: 대화와 맞는 정도에 개념별 상태만큼 곱해 더한다. 지금 말한 개념의 선행 개념을 헷갈렸다면
그 선행 개념도 후보에 넣는다(예: 해시표가 헷갈렸던 사람이 "LRU는 해시맵으로 만든다"고 하면 해시표를 먼저).
시작 상태: 대화에서 뽑은 값을 쓰고, 개념별 상태에 맞춰 난이도를 정한다.
- new(새로 앎): 기본 단계부터
- confused(헷갈림): 헷갈리기 쉬운 단계에서 멈춘다(해시표는 충돌 순간, LRU는 교체 직전)
- familiar(익숙함): 어려운 상황(긴 체인, 조회로 바뀌는 교체 순서)부터
"""

from typing import Literal

from pydantic import BaseModel

from .concepts import CONCEPTS
from .extract import Analysis
from .states import HashState, LruOp, LruState

Level = Literal["basic", "tricky", "advanced"]

MIN_SCORE = 0.4
# 대화와 맞는 정도에 (1 + 이 값)을 곱한다. 더하지 않고 곱해야, 지난 개념이 지금 말하는 개념을 덮지 않는다
STATUS_BOOST = {"confused": 0.5, "new": 0.2, "familiar": 0.0}
PREREQ_BOOST = 0.2  # 헷갈렸던 선행 개념을 방금 말했을 때 더한다
PREREQ_FOLLOW = 0.8  # 헷갈렸던 선행 개념을 말하지 않았을 때, 지금 개념 점수에 이 비율을 곱해 바로 아래에 둔다
LEVEL_BY_STATUS: dict[str, Level] = {"new": "basic", "confused": "tricky", "familiar": "advanced"}
LEVEL_LABEL = {"basic": "기본 단계부터", "tricky": "헷갈리기 쉬운 단계에서", "advanced": "어려운 상황부터"}
STATUS_LABEL = {"new": "지난 평가에서 새로 알게 된 개념", "confused": "지난 평가에서 헷갈렸던 개념", "familiar": "이미 익숙한 개념"}


class Card(BaseModel):
    concept_id: str
    name: str
    question: str
    viz: str | None
    state: dict | None
    level: Level
    score: float
    reason: str


def recommend(analysis: Analysis, statuses: dict[str, str], limit: int = 3) -> list[Card]:
    context = {cid: s for cid, s in analysis.scores.items() if s >= MIN_SCORE}
    # 지금 말한 개념의 선행 개념 가운데 헷갈렸던 것. 대화에 나오지 않았어도 후보가 된다
    prereq_of: dict[str, tuple[str, float]] = {}
    for cid, s in sorted(context.items(), key=lambda kv: kv[1], reverse=True):
        for r in CONCEPTS[cid].related:
            if statuses.get(r) == "confused" and r not in prereq_of:
                prereq_of[r] = (cid, s)

    cards = []
    for cid in set(context) | set(prereq_of):
        concept = CONCEPTS[cid]
        status = statuses.get(cid)
        reasons = []
        score = 0.0
        if cid in context:
            score = context[cid] * (1 + STATUS_BOOST.get(status, 0.0))
            reasons.append("지금 대화에 나온 개념")
        if cid in prereq_of:
            parent, parent_score = prereq_of[cid]
            if cid in analysis.latest:
                score += PREREQ_BOOST
            else:
                score = max(score, parent_score * PREREQ_FOLLOW)
            reasons.append(f"{CONCEPTS[parent].name}을 이해하는 데 먼저 필요한 개념")
        if status:
            reasons.append(STATUS_LABEL[status])
        level: Level = LEVEL_BY_STATUS.get(status, "basic")
        state = start_state(concept.viz, analysis.states.get(cid), level) if concept.viz else None
        if concept.viz:
            reasons.append(f"{LEVEL_LABEL[level]} 연다")
        cards.append(
            Card(
                concept_id=cid,
                name=concept.name,
                question=concept.question,
                viz=concept.viz,
                state=state,
                level=level,
                score=round(score, 3),
                reason=" · ".join(reasons),
            )
        )
    cards.sort(key=lambda c: c.score, reverse=True)
    return cards[:limit]


def start_state(viz: str, from_talk: dict | None, level: Level) -> dict:
    if viz == "hash":
        return hash_start(HashState.model_validate(from_talk) if from_talk else None, level).model_dump()
    if viz == "lru":
        return lru_start(LruState.model_validate(from_talk) if from_talk else None, level).model_dump()
    raise ValueError(f"알 수 없는 시각화: {viz}")


def hash_start(talk: HashState | None, level: Level) -> HashState:
    size = talk.size if talk else 10
    keys = list(talk.keys) if talk else []
    focus = talk.focus if talk else "insert"
    lookup = talk.lookup if talk else None
    if not keys:
        keys = [3, 7, 12]
    if level == "tricky":
        if not _has_collision(keys, size):
            keys.append(keys[0] + size)  # 같은 칸에 들어가는 키를 하나 더한다
        if focus == "insert":
            focus = "collision"
    elif level == "advanced":
        # 한 칸에 키가 몰려 체인이 길어지고 조회가 느려지는 상태
        base = keys[0] % size
        keys += [base + size * i for i in range(1, 5) if base + size * i not in keys]
        focus = "long_chain"
        lookup = lookup if lookup is not None else keys[-1]
    return HashState(size=size, keys=keys[:16], focus=focus, lookup=lookup)


def _has_collision(keys: list[int], size: int) -> bool:
    slots = [k % size for k in keys]
    return len(set(slots)) < len(slots)


def lru_start(talk: LruState | None, level: Level) -> LruState:
    capacity = talk.capacity if talk else 3
    ops = list(talk.ops) if talk else []
    if not ops:
        ops = [LruOp(op="put", key=k) for k in "ABC"]
    if level == "tricky":
        # 처음 교체가 일어나기 직전에서 멈춰, 다음에 누가 밀려날지 먼저 생각해 보게 한다
        _fill_to(ops, capacity + 1)
        ops = ops[:16]
        return LruState(capacity=capacity, ops=ops, stop_at=_first_eviction(ops, capacity))
    if level == "advanced":
        # 가장 먼저 넣었지만 방금 조회한 키는 살아남고, 다른 키가 밀려나는 상황
        _fill_to(ops, capacity)
        ops.append(LruOp(op="get", key=ops[0].key))
        _fill_to(ops, capacity + 1)
        ops = ops[:16]
        return LruState(capacity=capacity, ops=ops, stop_at=len(ops))
    return LruState(capacity=capacity, ops=ops[:16], stop_at=talk.stop_at if talk else None)


def _first_eviction(ops: list[LruOp], capacity: int) -> int:
    """처음 교체를 일으키는 연산의 번호(0부터). 그 앞까지 실행한 상태가 된다."""
    order: list[str] = []
    for i, o in enumerate(ops):
        if o.key in order:
            order.remove(o.key)
        elif o.op == "get":
            continue
        order.insert(0, o.key)
        if len(order) > capacity:
            return i
    return len(ops)


def _fill_to(ops: list[LruOp], distinct_keys: int) -> None:
    """서로 다른 키가 distinct_keys개가 될 때까지 새 키를 넣는다."""
    used = {o.key for o in ops}
    for k in "ABCDEFGHIJKL":
        if len(used) >= distinct_keys:
            return
        if k not in used:
            ops.append(LruOp(op="put", key=k))
            used.add(k)
