# concept-viz

동료 평가 대화를 듣고, 지금 이야기하는 컴퓨터공학 개념의 인터랙티브 시각화를 추천한다. 시각화는 대화에 나온 값과, 피평가자의 지난 동료 평가 피드백에 맞춘 시작 상태로 열린다. 기획은 [docs/기획.md](docs/기획.md)에 있다.

## 웹 데모

https://feelosophysics.github.io/athon/ (두 학습자 비교 화면으로 열린다)

서버 없이 브라우저 안에서 [Pyodide](https://pyodide.org)로 `app/`의 파이썬 코드를 그대로 돌린다(`web/pyapi.js`). 처음 열 때 엔진을 받느라 10초 남짓 걸린다. LLM과 STT 없이 규칙 기반 경로로 돌고, 대화는 글로 입력한다. 평가 화면은 [web/index.html](https://feelosophysics.github.io/athon/web/)이다.

## 실행

```bash
uv sync
uv run uvicorn app.main:app --port 8790
```

http://127.0.0.1:8790 을 연다. LLM과 STT를 설정하지 않으면 규칙 기반 경로로 돌고, 대화는 글로 입력한다.

### L4 서버에서

```bash
uv sync --extra stt
export STT_MODEL=large-v3            # faster-whisper 모델
export LLM_BASE_URL=http://127.0.0.1:8000/v1   # vLLM 등 OpenAI 호환 서버
export LLM_MODEL=<서빙한 모델 이름>
uv run uvicorn app.main:app --host 0.0.0.0 --port 8790
```

L4 한 장(약 22.5GiB)에 Whisper(fp16)와 8B LLM을 함께 올리려면 LLM을 4비트로 양자화한다.

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `LLM_BASE_URL` | 없음 | 없으면 규칙 기반 경로 |
| `LLM_MODEL` | `default` | |
| `LLM_API_KEY` | `none` | |
| `STT_MODEL` | 없음 | 없으면 글 입력 |
| `STT_DEVICE` / `STT_COMPUTE_TYPE` | `cuda` / `float16` | |
| `DATA_PATH` | `data/store.json` | 개념별 상태와 평가 기록 |

## 구조

```text
app/
  concepts.py   추천 후보 개념, 키워드, 확인 질문
  extract.py    최근 발화들 → 개념 점수, 시각화 시작 상태 (LLM, 실패하면 규칙)
  numbers.py    말로 한 숫자("십삼", "세 개") → 아라비아 숫자
  profile.py    피드백 → 이름 지우기 → 개념별 상태(new/confused/familiar)
  recommend.py  점수와 개념별 상태 → 카드 순위, 난이도별 시작 상태
  states.py     시작 상태 형식(LLM 출력 검증)
  stt.py        faster-whisper 받아 적기
  store.py      JSON 저장
  service.py    API가 하는 일(서버와 브라우저 데모가 함께 쓴다)
  main.py       FastAPI 라우트와 정적 파일
web/
  app.js        평가 준비, 녹음(10초 구간), 추천 카드
  compare.html  같은 대화를 두 학습자에게 넣고 추천을 나란히 비교(시연용, 저장 없음)
  pyapi.js      서버가 없으면 Pyodide로 app/ 코드를 브라우저에서 돌려 /api에 답한다
  summary.js    카드 요약 문구
  viz/hash.js   체이닝 해시표
  viz/lru.js    LRU 캐시
```

## API

- `POST /api/profile` `{learner, feedback, save?}` → 개념별 상태. 피드백 원문은 저장하지 않는다. `save: false`면 상태도 저장하지 않는다.
- `POST /api/analyze` `{learner, lines, statuses?}` → 추천 카드 목록. `statuses`를 주면 저장된 상태 대신 쓴다. `lines`는 최근 발화 최대 5개이고, 값은 그 개념을 말한 발화와 이어지는 후속 발화에서만 뽑는다.
- `POST /api/transcribe` (multipart `audio`) → `{text}`. 녹음은 받아 적은 직후 지운다.
- `POST /api/session/end` `{learner, concepts, opened}` → 다룬 개념과 펼친 카드만 기록
- `GET /api/health` → LLM·STT 연결 여부

## 시작 상태 규칙

| 개념별 상태 | 순위 | 해시표 | LRU |
|---|---|---|---|
| 없음 / 새로 앎 | ×1 / ×1.2 | 대화의 키로 끝까지 넣은 상태 | 대화의 연산 그대로 |
| 헷갈림 | ×1.5 | 처음 충돌하는 순간에서 멈춤 | 처음 교체가 일어나기 직전에서 멈춤(누가 밀려날지 먼저 생각) |
| 익숙함 | ×1 | 한 칸에 키가 몰려 체인이 길어진 상태에서 조회 | 조회한 오래된 키가 살아남고 다른 키가 밀려나는 상황 |

순위는 대화와 맞는 정도에 위 배수를 곱한다. 지금 말한 개념의 선행 개념(예: LRU의 해시표)을 헷갈렸다면, 대화에 나오지 않았어도 그 선행 개념을 후보에 넣는다. 선행 개념을 방금 말했으면 +0.2를 더해 먼저 띄우고, 말하지 않았으면 지금 개념 바로 아래에 둔다.

## 테스트

```bash
uv run pytest
```
