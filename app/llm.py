"""OpenAI 호환 API로 LLM을 부른다.

L4 서버에서는 vLLM 등으로 오픈 8B 모델(4비트)을 띄우고 LLM_BASE_URL에 그 주소를 넣는다.
LLM_BASE_URL이 없으면 enabled()가 False이고, 호출하는 쪽이 규칙 기반 경로로 돈다.
httpx는 부를 때만 가져온다. 서버 없이 브라우저(Pyodide)에서 돌 때는 httpx가 없다.
"""

import json
import os

TIMEOUT_SECONDS = 20


def enabled() -> bool:
    return bool(os.environ.get("LLM_BASE_URL"))


def complete_json(system: str, user: str) -> dict | None:
    """JSON 객체 하나를 돌려받는다. 실패하면 None을 돌려 호출한 쪽이 규칙으로 대신하게 한다."""
    if not enabled():
        return None
    import httpx

    base = os.environ["LLM_BASE_URL"].rstrip("/")
    payload = {
        "model": os.environ.get("LLM_MODEL", "default"),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {os.environ.get('LLM_API_KEY', 'none')}"}
    try:
        r = httpx.post(f"{base}/chat/completions", json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError):
        return None
