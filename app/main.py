from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from . import llm, service, stt
from .service import AnalyzeIn, AnalyzeOut, ProfileIn, ProfileOut, SessionEndIn

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="concept-viz")


@app.get("/api/health")
def health():
    return {"llm": llm.enabled(), "stt": stt.enabled(), "concepts": service.concept_names()}


@app.post("/api/profile", response_model=ProfileOut)
def post_profile(body: ProfileIn):
    return service.post_profile(body)


@app.get("/api/profile/{learner}")
def get_profile(learner: str):
    return service.get_profile(learner)


@app.post("/api/analyze", response_model=AnalyzeOut)
def post_analyze(body: AnalyzeIn):
    return service.post_analyze(body)


@app.post("/api/transcribe")
def post_transcribe(audio: UploadFile = File(...)):
    # 일반 def라서 FastAPI가 스레드에서 돌린다. 받아 적는 동안 다른 요청이 막히지 않는다
    if not stt.enabled():
        raise HTTPException(503, "STT 서버가 설정되지 않았다. STT_MODEL을 지정하고 faster-whisper를 설치한다.")
    data = audio.file.read()
    suffix = Path(audio.filename or "chunk.webm").suffix or ".webm"
    return {"text": stt.transcribe(data, suffix)}


@app.post("/api/session/end")
def post_session_end(body: SessionEndIn):
    return service.post_session_end(body)


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
