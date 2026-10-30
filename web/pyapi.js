// 서버가 없을 때(GitHub Pages 등) /api 요청에 브라우저 안에서 답한다.
// Pyodide로 app/ 의 파이썬 코드를 그대로 돌리므로, 서버와 추천 결과가 같다.
// 서버가 있으면(uvicorn으로 띄웠을 때) 아무것도 바꾸지 않고 요청을 그대로 보낸다.
(() => {
  const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";
  const MODULES = ["__init__", "concepts", "numbers", "states", "llm", "extract", "profile", "recommend", "store", "service"];
  const GLUE = `
import json, os, sys
from urllib.parse import unquote
sys.path.insert(0, "/home/pyodide")
os.environ["DATA_PATH"] = "/tmp/store.json"  # 브라우저 메모리. 새로고침하면 사라진다
from pydantic import ValidationError
from app import service

def handle(method, path, body_json):
    body = json.loads(body_json) if body_json else None
    try:
        if path == "/api/health":
            out = {"llm": False, "stt": False, "browser": True, "concepts": service.concept_names()}
        elif path == "/api/profile" and method == "POST":
            out = service.post_profile(service.ProfileIn.model_validate(body)).model_dump()
        elif path.startswith("/api/profile/"):
            out = service.get_profile(unquote(path[len("/api/profile/"):]))
        elif path == "/api/analyze":
            out = service.post_analyze(service.AnalyzeIn.model_validate(body)).model_dump()
        elif path == "/api/session/end":
            out = service.post_session_end(service.SessionEndIn.model_validate(body))
        else:
            return json.dumps({"status": 503, "body": {"detail": "브라우저 데모에서는 쓸 수 없다"}})
    except ValidationError as e:
        return json.dumps({"status": 422, "body": {"detail": str(e)}})
    return json.dumps({"status": 200, "body": out}, ensure_ascii=False)
`;

  const realFetch = window.fetch.bind(window);
  let modePromise = null;
  let enginePromise = null;

  async function detectMode() {
    try {
      const r = await realFetch("/api/health");
      if (r.ok && (r.headers.get("content-type") || "").includes("json")) return "server";
    } catch {}
    return "browser";
  }

  function banner(text, isError = false) {
    let el = document.getElementById("pyapi-banner");
    if (!el) {
      el = document.createElement("div");
      el.id = "pyapi-banner";
      el.style.cssText = "position:fixed;left:50%;top:12px;transform:translateX(-50%);z-index:9999;width:max-content;max-width:calc(100% - 32px);padding:8px 14px;border-radius:8px;font-size:13px;box-shadow:0 2px 10px rgba(0,0,0,.12)";
      document.body.append(el);
    }
    el.style.background = isError ? "#fff0e6" : "#e8efff";
    el.style.color = isError ? "#d9480f" : "#2f6fed";
    el.textContent = text;
    el.hidden = !text;
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error(`불러오기 실패: ${src}`));
      document.head.append(s);
    });
  }

  async function startEngine() {
    // 서버 없이 추천 코드를 돌리려고 브라우저에 파이썬을 내려받는다. 무엇을 하는지와 걸린 시간을 보여 준다
    const started = Date.now();
    let stage = "";
    const show = () => banner(`추천 엔진 준비 중 · ${stage} · ${Math.round((Date.now() - started) / 1000)}초 (처음 한 번 10초 남짓, 끝나면 이 알림이 사라집니다)`);
    const tick = setInterval(show, 1000);
    const step = (text) => { stage = text; show(); };
    try {
      step("1/3 브라우저용 파이썬 내려받기");
      await loadScript(PYODIDE + "pyodide.js");
      const py = await window.loadPyodide({ indexURL: PYODIDE });
      step("2/3 필요한 패키지 설치");
      await py.loadPackage("pydantic");
      step("3/3 추천 코드 불러오기");
      py.FS.mkdirTree("/home/pyodide/app");
      for (const m of MODULES) {
        const res = await realFetch(new URL(`../app/${m}.py`, location.href));
        if (!res.ok) throw new Error(`app/${m}.py ${res.status}`);
        py.FS.writeFile(`/home/pyodide/app/${m}.py`, await res.text());
      }
      py.runPython(GLUE);
      banner("");
      return py.globals.get("handle");
    } catch (err) {
      banner(`추천 엔진을 불러오지 못했습니다(${err.message}). 새로고침해 보세요.`, true);
      throw err;
    } finally {
      clearInterval(tick);
    }
  }

  window.fetch = async (input, init = {}) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (!url.pathname.startsWith("/api/")) return realFetch(input, init);
    modePromise ??= detectMode();
    if ((await modePromise) === "server") return realFetch(input, init);
    const handle = await (enginePromise ??= startEngine());
    const body = typeof init.body === "string" ? init.body : null;
    const res = JSON.parse(handle(init.method || "GET", url.pathname, body));
    return new Response(JSON.stringify(res.body), { status: res.status, headers: { "Content-Type": "application/json" } });
  };
})();
