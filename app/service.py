"""API가 하는 일을 웹 프레임워크 없이 모아 둔다.

서버(main.py)와, 서버 없이 브라우저에서 Pyodide로 도는 웹 데모(web/pyapi.js)가 같은 함수를 부른다.
"""

from pydantic import BaseModel, Field, field_validator

from . import store
from .concepts import CONCEPTS
from .extract import analyze
from .profile import Finding, Status, classify_feedback
from .recommend import Card, recommend


class ProfileIn(BaseModel):
    learner: str = Field(min_length=1, max_length=40)
    feedback: str = Field(min_length=1, max_length=20_000)
    save: bool = True  # 비교 화면은 저장하지 않고 분류 결과만 받는다


class ProfileOut(BaseModel):
    statuses: dict[str, str]
    findings: list[Finding]


class AnalyzeIn(BaseModel):
    learner: str = Field(min_length=1, max_length=40)
    lines: list[str] = Field(max_length=5)  # 최근 발화들. 마지막이 가장 최근
    statuses: dict[str, Status] | None = None  # 주면 저장된 상태 대신 쓴다(비교 화면)

    @field_validator("lines")
    @classmethod
    def cut_long_lines(cls, v: list[str]) -> list[str]:
        return [line[:1_000] for line in v]


class AnalyzeOut(BaseModel):
    cards: list[Card]
    source: str


class SessionEndIn(BaseModel):
    learner: str = Field(min_length=1, max_length=40)
    mission: str = "B5-1"
    concepts: list[str] = []
    opened: list[str] = []


def concept_names() -> dict[str, str]:
    return {c.id: c.name for c in CONCEPTS.values()}


def post_profile(body: ProfileIn) -> ProfileOut:
    findings = classify_feedback(body.feedback)
    found = {f.concept_id: f.status for f in findings}
    statuses = store.set_statuses(body.learner, found) if body.save else found
    return ProfileOut(statuses=statuses, findings=findings)


def get_profile(learner: str) -> dict:
    return {"statuses": store.get_statuses(learner)}


def post_analyze(body: AnalyzeIn) -> AnalyzeOut:
    result = analyze(body.lines)
    statuses = body.statuses if body.statuses is not None else store.get_statuses(body.learner)
    return AnalyzeOut(cards=recommend(result, statuses), source=result.source)


def post_session_end(body: SessionEndIn) -> dict:
    store.add_session(body.learner, body.mission, body.concepts, body.opened)
    return {"ok": True}
