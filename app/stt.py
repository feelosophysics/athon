"""받아 적기. L4 서버에서 faster-whisper로 돈다.

STT_MODEL(예: large-v3)이 없거나 faster-whisper가 설치되지 않았으면 enabled()가 False다.
이때 화면은 글 입력으로 대신한다.
"""

import os
import tempfile
from functools import lru_cache

from .concepts import CONCEPTS

# 전문 용어를 미리 알려 주면 "체이닝"을 "체인잉"으로 적는 식의 오류가 줄어든다
INITIAL_PROMPT = "코디세이 동료 평가 대화. " + ", ".join(
    kw for c in CONCEPTS.values() for kw in c.keywords[:4]
)


def enabled() -> bool:
    if not os.environ.get("STT_MODEL"):
        return False
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _model():
    from faster_whisper import WhisperModel

    return WhisperModel(
        os.environ["STT_MODEL"],
        device=os.environ.get("STT_DEVICE", "cuda"),
        compute_type=os.environ.get("STT_COMPUTE_TYPE", "float16"),
    )


def transcribe(audio: bytes, suffix: str = ".webm") -> str:
    # 녹음 원문은 받아 적은 직후 지운다
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio)
        path = f.name
    try:
        segments, _ = _model().transcribe(path, language="ko", initial_prompt=INITIAL_PROMPT, vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()
    finally:
        os.remove(path)
