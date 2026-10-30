import pytest

from app.numbers import normalize_numbers


@pytest.mark.parametrize("spoken,expected", [
    ("삼이랑 십삼", "3이랑 13"),
    ("십이랑 십칠이 겹치나", "10이랑 17이 겹치나"),
    ("이십오를 찾으면", "25를 찾으면"),
    ("크기가 일곱이면", "크기가 7이면"),
    ("용량이 세 개일 때", "용량이 3개일 때"),
    ("삼, 육, 구 넣고", "3, 6, 9 넣고"),
])
def test_spoken_numbers(spoken, expected):
    assert normalize_numbers(spoken) == expected


@pytest.mark.parametrize("talk", [
    "두 키 사이에 들어가",
    "구이 먹으러 가자",
    "네 맞아요",
    "세상에 나쁜 개는 없다",
    "이 칸에 넣어",
    "일단 십자가 모양으로",
])
def test_everyday_words_untouched(talk):
    assert normalize_numbers(talk) == talk
