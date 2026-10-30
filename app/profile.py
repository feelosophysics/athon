"""동료 평가 피드백에서 개념별 상태(새로 앎 / 헷갈림 / 익숙함)를 뽑는다.

피드백에는 다른 학습자의 이름과 글이 들어 있다. 이름을 먼저 지우고, 저장하는 것은 개념별 상태뿐이다.
"""

import re
from typing import Literal

from pydantic import BaseModel

from . import llm
from .concepts import CONCEPTS, concept_list_for_prompt, keyword_score

Status = Literal["new", "confused", "familiar"]


class Finding(BaseModel):
    concept_id: str
    status: Status
    evidence: str  # 이름을 지운 근거 문장. 화면에만 보여 주고 저장하지 않는다


# ---- 이름 지우기 ----

NAME_LINE_PATTERNS = [
    re.compile(r"^\s*[가-힣]{2,4}\s*$"),  # 이름만 있는 줄
    re.compile(r"^\s*[가-힣]{2,4}\s*·\s*\d{4}-\d{2}-\d{2}.*$"),  # "이름 · 날짜"
    re.compile(r"^\s*\S+@\S*\s*$"),  # 계정 줄
]
INLINE_NAME_PATTERNS = [
    (re.compile(r"동료\([가-힣]{2,4}\)"), "동료"),
    (re.compile(r"[가-힣]{2,4}님"), "상대"),
]


def scrub_names(text: str) -> str:
    lines = [line for line in text.splitlines() if not any(p.match(line) for p in NAME_LINE_PATTERNS)]
    out = "\n".join(lines)
    for pattern, repl in INLINE_NAME_PATTERNS:
        out = pattern.sub(repl, out)
    return out


# ---- 분류 ----

SYSTEM_PROMPT = """너는 코디세이 동료 평가 피드백을 읽고, 피평가자가 개념마다 어떤 상태인지 분류한다.
- new: 이번에 처음 알게 되었다
- confused: 헷갈렸거나, 설명하지 못했거나, 어렵다고 했다
- familiar: 이미 잘 알거나, 막힘없이 설명했다
후보 개념 목록에 있는 id만 쓴다. 근거 문장이 없는 개념은 넣지 않는다. 태도나 감상만 있는 문장은 무시한다.

후보 개념:
{concepts}

다음 JSON만 출력한다:
{{"findings": [{{"concept_id": "...", "status": "new"|"confused"|"familiar", "evidence": "근거 문장"}}]}}"""

STATUS_MARKERS: list[tuple[Status, re.Pattern]] = [
    ("confused", re.compile(r"헷갈|모르겠|어려웠|어렵|이해가 안|설명하지 못|막혔|헤맸")),
    ("new", re.compile(r"처음 알|새로 알|처음 들|몰랐|알게 되")),
    ("familiar", re.compile(r"잘 알|익숙|쉽게|막힘없|설명해 주|이미 알")),
]


def classify_feedback(feedback: str) -> list[Finding]:
    text = scrub_names(feedback)
    raw = llm.complete_json(SYSTEM_PROMPT.format(concepts=concept_list_for_prompt()), text)
    if raw is not None:
        findings = []
        for item in raw.get("findings") or []:
            try:
                f = Finding.model_validate(item)
            except ValueError:
                continue
            if f.concept_id in CONCEPTS:
                findings.append(f)
        if findings:
            return _dedupe(findings)
    return classify_with_rules(text)


def classify_with_rules(text: str) -> list[Finding]:
    findings = []
    for sentence in re.split(r"[\n.!?]+", text):
        lowered = sentence.lower()
        status = next((s for s, p in STATUS_MARKERS if p.search(sentence)), None)
        if status is None:
            continue
        for c in CONCEPTS.values():
            if keyword_score(c, lowered) > 0:
                findings.append(Finding(concept_id=c.id, status=status, evidence=sentence.strip()))
    return _dedupe(findings)


SEVERITY = {"confused": 3, "new": 2, "familiar": 1}


def _dedupe(findings: list[Finding]) -> list[Finding]:
    """같은 개념이 여러 번 나오면 더 도움이 필요한 쪽(헷갈림 > 새로 앎 > 익숙함)을 남긴다."""
    best: dict[str, Finding] = {}
    for f in findings:
        if f.concept_id not in best or SEVERITY[f.status] > SEVERITY[best[f.concept_id].status]:
            best[f.concept_id] = f
    return list(best.values())
