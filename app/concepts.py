"""추천 후보가 되는 개념 목록.

시각화가 있는 개념은 B5-1의 해시표와 LRU다. 시각화가 없는 개념은 확인 질문만 추천한다.
strong은 그 개념에서만 쓰는 말이고, weak은 일상 대화에도 나오는 말이다.
LLM 없이 돌 때 strong이 하나 이상 있거나 weak이 둘 이상 있어야 그 개념으로 본다.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Concept:
    id: str
    name: str
    mission: str
    strong: tuple[str, ...]
    weak: tuple[str, ...]
    question: str
    viz: str | None = None  # web/viz/ 아래 시각화 이름. 없으면 질문 카드만 띄운다
    related: tuple[str, ...] = field(default_factory=tuple)

    @property
    def keywords(self) -> tuple[str, ...]:
        return self.strong + self.weak


CONCEPTS: dict[str, Concept] = {
    c.id: c
    for c in [
        Concept(
            id="hash_chaining",
            name="해시표와 충돌 해결(체이닝)",
            mission="B5-1",
            strong=("해시", "해쉬", "hash", "버킷", "체이닝", "chaining"),
            weak=("칸", "충돌", "나머지", "모듈로", "테이블"),
            question="두 키가 같은 칸에 들어가면 조회할 때 무슨 일이 일어나나요?",
            viz="hash",
        ),
        Concept(
            id="lru",
            name="LRU 캐시(이중 연결 리스트 + 해시맵)",
            mission="B5-1",
            strong=("lru", "엘알유", "캐시", "cache", "evict", "축출"),
            weak=("가장 오래", "최근", "교체", "연결 리스트", "용량"),
            question="LRU에서 조회만 해도 순서가 바뀌는 이유는 무엇인가요?",
            viz="lru",
            related=("hash_chaining",),
        ),
        Concept(
            id="heap_ttl",
            name="힙으로 TTL 만료 관리",
            mission="B5-1",
            strong=("힙", "heap", "ttl", "우선순위 큐", "priority queue"),
            weak=("만료",),
            question="만료 시간이 가장 빠른 항목을 힙에서 꺼내는 데 시간이 얼마나 걸리나요?",
        ),
        Concept(
            id="git_branch",
            name="Git 브랜치(커밋을 가리키는 포인터)",
            mission="B2-2",
            strong=("브랜치", "branch"),
            weak=("커밋", "commit", "포인터", "head"),
            question="브랜치를 새로 만들면 파일이 복사되나요, 무엇이 생기나요?",
        ),
        Concept(
            id="commit_dag",
            name="커밋 그래프(DAG)와 조상 탐색",
            mission="B5-2",
            strong=("dag", "조상", "위상 정렬", "머지 커밋", "부모 커밋"),
            weak=("그래프", "커밋", "부모"),
            question="머지 커밋의 부모는 몇 개이고, 조상은 어떻게 찾나요?",
            related=("git_branch",),
        ),
        Concept(
            id="db_join",
            name="PK/FK와 JOIN",
            mission="B6-1",
            strong=("조인", "join", "외래 키", "외래키", "foreign key", "기본 키", "기본키", "primary key"),
            weak=("fk", "pk", "1:n", "일대다", "테이블"),
            question="두 테이블을 JOIN할 때 어떤 열끼리 맞추나요?",
        ),
        Concept(
            id="iam",
            name="IAM과 최소 권한",
            mission="B3-1",
            strong=("iam", "최소 권한", "책임 분리"),
            weak=("권한", "정책", "role", "역할", "보안그룹"),
            question="보안그룹과 IAM은 각각 무엇을 막나요?",
        ),
    ]
}


def keyword_score(concept: Concept, lowered_text: str) -> float:
    strong = sum(1 for kw in concept.strong if kw in lowered_text)
    weak = sum(1 for kw in concept.weak if kw in lowered_text)
    if strong:
        return min(1.0, 0.5 + 0.15 * (strong - 1) + 0.1 * weak)
    if weak >= 2:
        return 0.4
    return 0.0


def concept_list_for_prompt() -> str:
    return "\n".join(f"- {c.id}: {c.name} (키워드: {', '.join(c.strong[:5])})" for c in CONCEPTS.values())
