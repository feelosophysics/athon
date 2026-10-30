"""말로 한 숫자를 아라비아 숫자로 바꾼다.

STT는 "삼이랑 십삼", "용량이 세 개"처럼 숫자를 한글로 적기도 한다.
"사이", "구이", "네(대답)"처럼 숫자 글자로 된 일상어를 숫자로 바꾸지 않도록, 바꾸는 경우를 좁게 잡는다.
"""

import re

SINO_DIGITS = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
NATIVE_WORDS = {"하나": 1, "셋": 3, "넷": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9}
NATIVE_COUNTERS = {"한": 1, "두": 2, "세": 3, "네": 4, "열": 10}

_NOT_HANGUL_BEFORE = r"(?<![가-힣])"
_END = r"(?![가-힣])"
PARTICLES = r"(?:이랑|랑|과|와|하고|이면|이야|이고|으로|로|에|이|가|을|를|은|는|도|만|번|칸|개)?"

# 십이나 백이 들어간 여러 글자 수(십삼, 이십오)는 일상어와 헷갈릴 일이 드물다.
# 끝자리를 게으르게 잡아 "십이랑"을 "십 + 이랑"(10)으로 읽는다
MULTI_SINO = re.compile(_NOT_HANGUL_BEFORE + r"([일이삼사오육칠팔구]?백?[일이삼사오육칠팔구]?십[일이삼사오육칠팔구]??|[일이삼사오육칠팔구]?백[일이삼사오육칠팔구]??)(?=" + PARTICLES + _END + ")")
# 한 글자 수는 나열할 때만 바꾼다: "삼이랑", "삼, 육"
SINGLE_SINO = re.compile(_NOT_HANGUL_BEFORE + r"([삼육칠팔구])(?=(?:이랑|랑|과|와|하고)" + _END + r"|\s*,)")
SINGLE_SINO_LAST = re.compile(r"(?<=,)(\s*)([삼육칠팔구])(?=(?:을|를|도|만)?" + _END + ")")  # 나열의 마지막: "삼, 육, 구 넣고"
NATIVE = re.compile(_NOT_HANGUL_BEFORE + "(" + "|".join(NATIVE_WORDS) + ")(?=" + PARTICLES + _END + ")")
NATIVE_COUNT = re.compile(_NOT_HANGUL_BEFORE + "(" + "|".join(NATIVE_COUNTERS) + r")\s*(?=개|칸)")


def sino_value(word: str) -> int:
    total, current = 0, 0
    for ch in word:
        if ch == "백":
            total += (current or 1) * 100
            current = 0
        elif ch == "십":
            total += (current or 1) * 10
            current = 0
        else:
            current = SINO_DIGITS[ch]
    return total + current


def normalize_numbers(text: str) -> str:
    text = NATIVE_COUNT.sub(lambda m: str(NATIVE_COUNTERS[m.group(1)]), text)
    text = NATIVE.sub(lambda m: str(NATIVE_WORDS[m.group(1)]), text)
    text = MULTI_SINO.sub(lambda m: str(sino_value(m.group(1))), text)
    text = SINGLE_SINO.sub(lambda m: str(SINO_DIGITS[m.group(1)]), text)
    text = SINGLE_SINO_LAST.sub(lambda m: m.group(1) + str(SINO_DIGITS[m.group(2)]), text)
    return text
