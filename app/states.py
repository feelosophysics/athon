"""시각화의 시작 상태 형식.

LLM은 이 형식만 채운다. 형식에 맞지 않으면 버리고 기본 예시로 연다.
"""

from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

HashFocus = Literal["insert", "collision", "lookup", "long_chain"]


class HashState(BaseModel):
    size: int = Field(10, ge=2, le=16)
    keys: list[int] = Field(default_factory=list, max_length=16)
    focus: HashFocus = "insert"
    lookup: int | None = None

    @field_validator("keys")
    @classmethod
    def non_negative(cls, v: list[int]) -> list[int]:
        return [k for k in v if 0 <= k < 10_000]


class LruOp(BaseModel):
    op: Literal["put", "get"]
    key: str = Field(min_length=1, max_length=4)


class LruState(BaseModel):
    capacity: int = Field(3, ge=2, le=6)
    ops: list[LruOp] = Field(default_factory=list, max_length=16)
    stop_at: int | None = None  # 이 번호의 연산까지 실행한 상태로 연다. None이면 끝까지


STATE_MODELS = {"hash": HashState, "lru": LruState}


def parse_state(viz: str, raw: dict | None) -> BaseModel | None:
    if raw is None or viz not in STATE_MODELS:
        return None
    try:
        return STATE_MODELS[viz].model_validate(raw)
    except ValidationError:
        return None
