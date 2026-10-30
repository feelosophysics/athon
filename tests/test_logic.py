import pytest

from app import llm
from app.extract import analyze_with_rules, hash_state_from_text, lru_state_from_text
from app.profile import classify_with_rules, scrub_names
from app.recommend import hash_start, lru_start, recommend
from app.states import LruOp, LruState, parse_state


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    assert not llm.enabled()


def test_hash_values_from_talk():
    s = hash_state_from_text("크기 10인 해시표에 키 3과 13이 같은 칸에 들어가면?")
    assert s.size == 10
    assert s.keys == [3, 13]
    assert s.focus == "collision"


def test_lru_ops_with_korean_particles():
    s = lru_state_from_text("용량 3인 LRU에 A, B, C 넣고 A를 조회한 다음 D를 넣으면 뭐가 빠져?")
    assert s.capacity == 3
    assert [(o.op, o.key) for o in s.ops] == [("put", "A"), ("put", "B"), ("put", "C"), ("get", "A"), ("put", "D")]


def test_rules_pick_concept_and_skip_off_topic():
    assert "hash_chaining" in analyze_with_rules("해시 충돌 나면 체이닝으로 이어 붙이잖아").scores
    assert analyze_with_rules("DRM 걸린 영상 플레이어 얘기").scores == {}


def test_scrub_names():
    text = "홍길동\nabc@~\n김철수 · 2026-10-28 08:09\n동료(이영희) 의견\n철수님 덕분에 IAM을 처음 알게 되었다"
    out = scrub_names(text)
    for name in ["홍길동", "김철수", "이영희", "철수님"]:
        assert name not in out
    assert "IAM을 처음 알게 되었다" in out


def test_feedback_statuses():
    findings = {f.concept_id: f.status for f in classify_with_rules(
        "IAM 같은 책임 분리 설정을 처음 알게 되었네요.\n해시 충돌 설명이 헷갈렸습니다.\n태도가 친절했습니다."
    )}
    assert findings == {"iam": "new", "hash_chaining": "confused"}


def test_tricky_hash_always_shows_collision():
    s = hash_start(None, "tricky")
    slots = [k % s.size for k in s.keys]
    assert len(set(slots)) < len(slots)
    assert s.focus == "collision"


def test_advanced_hash_builds_long_chain():
    s = hash_start(None, "advanced")
    base = s.keys[0] % s.size
    assert sum(1 for k in s.keys if k % s.size == base) >= 4
    assert s.focus == "long_chain"


def test_tricky_lru_stops_just_before_first_eviction():
    s = lru_start(None, "tricky")
    assert len({o.key for o in s.ops}) == s.capacity + 1
    assert s.stop_at == len(s.ops) - 1  # 마지막 넣기가 교체를 일으킨다


def test_tricky_lru_keeps_talk_ops_and_stops_before_eviction():
    talk = LruState(capacity=3, ops=[LruOp(op=o, key=k) for o, k in [("put", "A"), ("put", "B"), ("put", "C"), ("get", "A"), ("put", "D")]])
    s = lru_start(talk, "tricky")
    assert [o.key for o in s.ops] == ["A", "B", "C", "A", "D"]
    assert s.stop_at == 4


def test_advanced_lru_get_saves_oldest_key():
    s = lru_start(None, "advanced")
    assert ("get", s.ops[0].key) in [(o.op, o.key) for o in s.ops]
    assert len({o.key for o in s.ops}) == s.capacity + 1


def test_same_talk_different_learner_different_start():
    analysis = analyze_with_rules("해시표에서 키 3과 13이 같은 칸에 들어가면?")
    plain = recommend(analysis, {})
    confused = recommend(analysis, {"hash_chaining": "confused"})
    familiar = recommend(analysis, {"hash_chaining": "familiar"})
    assert plain[0].level == "basic"
    assert confused[0].level == "tricky"
    assert familiar[0].level == "advanced"
    assert confused[0].score > plain[0].score
    assert plain[0].state["keys"][:2] == [3, 13]


# 같은 대화를 피드백이 다른 두 학습자에게 넣는 비교 시연 대본
A = {"hash_chaining": "confused", "lru": "new"}
B = {"hash_chaining": "familiar", "lru": "confused"}
SCRIPT = [
    "해시 테이블에 삼이랑 십삼 넣으면 같은 칸이잖아",
    "LRU 캐시는 해시맵이랑 연결 리스트로 만든다며?",
    "LRU 캐시 용량 3에 A, B, C 넣고 A 조회하고 D 넣으면?",
]


def run(lines, statuses):
    return recommend(analyze_with_rules(lines), statuses)


def test_compare_hash_collision_opens_differently():
    a, b = run(SCRIPT[:1], A), run(SCRIPT[:1], B)
    assert (a[0].level, b[0].level) == ("tricky", "advanced")
    assert a[0].state["keys"][:2] == b[0].state["keys"][:2] == [3, 13]


def test_compare_confused_prerequisite_comes_first():
    a, b = run(SCRIPT[:2], A), run(SCRIPT[:2], B)
    assert a[0].concept_id == "hash_chaining"
    assert "먼저 필요한 개념" in a[0].reason
    assert a[0].state["keys"][:2] == [3, 13]  # 앞에서 말한 값을 잃지 않는다
    assert b[0].concept_id == "lru"


def test_compare_current_topic_wins_when_prerequisite_not_mentioned_now():
    a, b = run(SCRIPT, A), run(SCRIPT, B)
    assert a[0].concept_id == b[0].concept_id == "lru"
    assert (a[0].level, b[0].level) == ("basic", "tricky")
    assert a[1].concept_id == "hash_chaining"


def test_prerequisite_added_even_if_not_mentioned():
    cards = run(["LRU 캐시 용량 3이면 뭐가 빠져?"], {"hash_chaining": "confused"})
    assert [c.concept_id for c in cards] == ["lru", "hash_chaining"]


def test_invalid_llm_state_is_rejected():
    assert parse_state("hash", {"size": 999, "keys": [1]}) is None
    assert parse_state("lru", {"ops": [{"op": "drop", "key": "A"}]}) is None
    assert parse_state("lru", {"ops": [LruOp(op="put", key="A").model_dump()]}) is not None
