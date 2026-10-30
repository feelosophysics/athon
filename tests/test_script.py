"""시연 대본과 실제 말투로 규칙 기반 경로를 점검한다.

STT는 숫자를 "삼", "십삼"처럼 한글로, 영문 키를 "에이", "비"처럼 적기도 한다.
"""

import pytest

from app import llm
from app.extract import analyze_with_rules


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    assert not llm.enabled()


def top(text):
    scores = analyze_with_rules(text).scores
    return max(scores, key=scores.get) if scores else None


HASH_CASES = [
    ("해시표에서 키 3과 13이 같은 칸에 들어가면 어떻게 돼?", 10, [3, 13], "collision"),
    ("해시 테이블에 삼이랑 십삼 넣으면 같은 칸이잖아", 10, [3, 13], "collision"),
    ("버킷이 7개인 해시 테이블에 10이랑 17을 넣으면 충돌 나지?", 7, [10, 17], "collision"),
    ("해시맵 크기가 일곱이면 십이랑 십칠이 겹치나?", 7, [10, 17], "collision"),
    ("해시표에 5, 15, 25 넣고 25를 찾으면 몇 번 비교해?", 10, [5, 15, 25], "lookup"),
]


@pytest.mark.parametrize("text,size,keys,focus", HASH_CASES)
def test_hash_script(text, size, keys, focus):
    a = analyze_with_rules(text)
    assert top(text) == "hash_chaining"
    s = a.states["hash_chaining"]
    assert (s["size"], s["keys"], s["focus"]) == (size, keys, focus)


LRU_CASES = [
    ("용량 3인 LRU에 A, B, C 넣고 A를 조회한 다음 D를 넣으면 뭐가 빠져?", 3, "A B C gA D"),
    ("LRU 캐시 용량이 세 개일 때 에이, 비, 씨 넣고 에이를 읽은 다음 디를 넣으면?", 3, "A B C gA D"),
    ("lru 캐시에 a, b 넣고 a 조회하고 c 넣으면 크기 2니까 b가 빠지지?", 2, "A B gA C"),
    ("LRU에 1, 2, 3 넣고 1을 다시 조회하고 4를 넣으면 용량 3이면 뭐가 나가?", 3, "1 2 3 g1 4"),
]


@pytest.mark.parametrize("text,capacity,ops", LRU_CASES)
def test_lru_script(text, capacity, ops):
    a = analyze_with_rules(text)
    assert top(text) == "lru"
    s = a.states["lru"]
    got = " ".join(("g" if o["op"] == "get" else "") + o["key"] for o in s["ops"])
    assert (s["capacity"], got) == (capacity, ops)


@pytest.mark.parametrize("text", [
    "최근에 배운 거 중에 제일 어려웠어",
    "이 칸 디자인 예쁘다",
    "역할 분담은 어떻게 했어?",
    "DRM 걸린 영상 플레이어 얘기 재밌네",
    "그래프 그려서 보여 주면 좋겠다",
])
def test_everyday_talk_gets_no_card(text):
    assert analyze_with_rules(text).scores == {}


@pytest.mark.parametrize("text,expected", [
    ("브랜치 만들면 커밋을 가리키는 포인터만 생기는 거지?", "git_branch"),
    ("머지 커밋은 부모가 둘이라 DAG가 되잖아", "commit_dag"),
    ("두 테이블을 외래 키로 JOIN하면", "db_join"),
    ("IAM 정책에서 최소 권한 원칙", "iam"),
    ("TTL 만료 시간을 힙으로 관리하면", "heap_ttl"),
])
def test_other_concepts(text, expected):
    assert top(text) == expected


def test_values_stay_with_their_concept():
    a = analyze_with_rules([
        "해시표에서 키 3과 13이 같은 칸에 들어가면?",
        "그럼 LRU 캐시는? 용량 3에 A, B, C 넣고 D 넣으면",
    ])
    assert a.states["hash_chaining"]["keys"] == [3, 13]
    assert a.scores["lru"] > a.scores["hash_chaining"]


def test_follow_up_without_keyword_extends_values():
    a = analyze_with_rules(["해시표에 키 3과 13 넣으면 충돌이지?", "23도 넣으면?"])
    assert a.states["hash_chaining"]["keys"] == [3, 13, 23]


def test_off_topic_line_does_not_extend_values():
    a = analyze_with_rules(["해시표에 키 3과 13 넣으면?", "LRU 캐시는 용량 2", "아 배고프다 12시네"])
    assert a.states["hash_chaining"]["keys"] == [3, 13]
