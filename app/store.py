"""피평가자별 개념 상태와 평가 기록을 JSON 파일 하나에 둔다.

녹음과 받아 적은 글, 피드백 원문은 저장하지 않는다.
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path

_lock = threading.Lock()


def _path() -> Path:
    return Path(os.environ.get("DATA_PATH", "data/store.json"))


def _load() -> dict:
    p = _path()
    if not p.exists():
        return {"learners": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _learner(data: dict, learner: str) -> dict:
    return data["learners"].setdefault(learner, {"statuses": {}, "sessions": []})


def get_statuses(learner: str) -> dict[str, str]:
    with _lock:
        return dict(_load()["learners"].get(learner, {}).get("statuses", {}))


def set_statuses(learner: str, statuses: dict[str, str]) -> dict[str, str]:
    with _lock:
        data = _load()
        merged = _learner(data, learner)["statuses"]
        merged.update(statuses)
        _save(data)
        return dict(merged)


def add_session(learner: str, mission: str, concepts: list[str], opened: list[str]) -> None:
    with _lock:
        data = _load()
        _learner(data, learner)["sessions"].append(
            {"at": datetime.now().isoformat(timespec="seconds"), "mission": mission, "concepts": concepts, "opened": opened}
        )
        _save(data)
