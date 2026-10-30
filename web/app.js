import * as hashViz from "./viz/hash.js";
import * as lruViz from "./viz/lru.js";
import { STATUS_LABEL, summarize } from "./summary.js";

const VIZ = { hash: hashViz, lru: lruViz };
const CHUNK_MS = 10_000; // 이 간격으로 녹음을 끊어 받아 적는다
const WINDOW = 3; // 최근 몇 구간을 묶어 분석할지
const MAX_CARDS = 6;

const $ = (s) => document.querySelector(s);
const state = { learner: "", lines: [], cards: [], active: null, opened: new Set(), seen: new Set(), recorder: null, stream: null, sttOn: false, conceptNames: {} };

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST",
    headers: body instanceof FormData ? {} : { "Content-Type": "application/json" },
    body: body instanceof FormData ? body : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json();
}

// ---- 준비 ----

async function loadHealth() {
  const h = await api("/api/health");
  state.sttOn = h.stt;
  state.conceptNames = h.concepts;
  $("#health").innerHTML = `<span class="${h.llm ? "on" : ""}">LLM ${h.llm ? "연결" : "규칙 대체"}</span><span class="${h.stt ? "on" : ""}">STT ${h.stt ? "연결" : "없음(글 입력)"}</span>`;
  if (h.browser) $("#health").insertAdjacentHTML("afterbegin", "<span>브라우저 데모(서버 없음)</span>");
}

function renderStatuses(statuses, findings = []) {
  const evidence = Object.fromEntries(findings.map((f) => [f.concept_id, f.evidence]));
  $("#statuses").innerHTML = "";
  for (const [cid, st] of Object.entries(statuses)) {
    const chip = document.createElement("span");
    chip.className = `chip ${st}`;
    chip.textContent = `${state.conceptNames[cid] ?? cid} · ${STATUS_LABEL[st] ?? st}`;
    if (evidence[cid]) chip.title = evidence[cid];
    $("#statuses").append(chip);
  }
}

$("#learner").addEventListener("change", async () => {
  const learner = $("#learner").value.trim();
  if (!learner) return;
  const p = await api(`/api/profile/${encodeURIComponent(learner)}`);
  renderStatuses(p.statuses);
  updateStart();
});

$("#profile-btn").addEventListener("click", async () => {
  const learner = $("#learner").value.trim();
  const feedback = $("#feedback").value.trim();
  if (!learner || !feedback) return alert("피평가자 이름과 피드백을 넣어 주세요.");
  const p = await api("/api/profile", { learner, feedback });
  $("#feedback").value = ""; // 원문은 화면에서도 지운다
  renderStatuses(p.statuses, p.findings);
  if (!p.findings.length) $("#statuses").insertAdjacentHTML("beforeend", '<span class="hint">개념 신호를 찾지 못했습니다. 대화 맥락만으로 추천합니다.</span>');
});

// 지어낸 예시 피드백. 처음 보는 사람이 분석 결과를 바로 볼 수 있게 한다
const FEEDBACK_EXAMPLE = `해시 충돌 처리를 설명할 때 체이닝이 헷갈려서 오래 걸렸습니다.
LRU 캐시는 이번에 처음 알게 되었어요.
Git 브랜치는 이미 잘 알고 막힘없이 설명했습니다.`;

$("#feedback-example").addEventListener("click", () => {
  if (!$("#learner").value.trim()) $("#learner").value = "학습자A";
  $("#feedback").value = FEEDBACK_EXAMPLE;
  updateStart();
});

function updateStart() {
  $("#start-btn").disabled = !($("#learner").value.trim() && $("#consent-a").checked && $("#consent-b").checked);
}
["#learner", "#consent-a", "#consent-b"].forEach((s) => $(s).addEventListener("input", updateStart));

$("#start-btn").addEventListener("click", async () => {
  state.learner = $("#learner").value.trim();
  $("#setup").hidden = true;
  $("#session").hidden = false;
  if (state.sttOn) await startRecording();
});

// ---- 녹음과 받아 적기 ----

async function startRecording() {
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    addLine("(마이크를 쓸 수 없어 글 입력으로 진행합니다)");
    return;
  }
  $("#rec").hidden = false;
  recordChunk();
}

function recordChunk() {
  // 구간마다 녹음기를 새로 만들어야 각 조각이 혼자 재생되는 파일이 된다
  if (!state.stream) return;
  const rec = new MediaRecorder(state.stream);
  const parts = [];
  rec.ondataavailable = (e) => parts.push(e.data);
  rec.onstop = async () => {
    if (state.stream) recordChunk();
    const blob = new Blob(parts, { type: rec.mimeType });
    if (blob.size < 2000) return;
    const form = new FormData();
    form.append("audio", blob, "chunk.webm");
    try {
      const { text } = await api("/api/transcribe", form);
      if (text) onUtterance(text);
    } catch (err) {
      console.error(err);
    }
  };
  rec.start();
  state.recorder = rec;
  setTimeout(() => rec.state === "recording" && rec.stop(), CHUNK_MS);
}

function stopRecording() {
  const stream = state.stream;
  state.stream = null;
  state.recorder?.state === "recording" && state.recorder.stop();
  stream?.getTracks().forEach((t) => t.stop());
  $("#rec").hidden = true;
}

$("#manual").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("#manual-text").value.trim();
  if (!text) return;
  $("#manual-text").value = "";
  onUtterance(text);
});

document.querySelectorAll("[data-line]").forEach((btn) => btn.addEventListener("click", () => onUtterance(btn.dataset.line)));

// ---- 추천 ----

function addLine(text) {
  const li = document.createElement("li");
  li.textContent = text;
  $("#transcript").append(li);
  li.scrollIntoView({ block: "end" });
}

async function onUtterance(text) {
  addLine(text);
  state.lines.push(text);
  const { cards } = await api("/api/analyze", { learner: state.learner, lines: state.lines.slice(-WINDOW) });
  const miss = $("#no-match");
  miss.hidden = cards.length > 0;
  miss.textContent = "최근 대화에서 아는 개념을 찾지 못했습니다. 아래 예시처럼 개념 이름과 값을 넣어 보세요. 예: “해시표에 5, 15, 25 넣고 25를 찾으면 몇 번 비교해?”";
  mergeCards(cards);
}

function mergeCards(incoming) {
  // 같은 개념이 같은 값으로 다시 나오면 자리를 지킨다. 새 개념이거나 대화의 값이 바뀌었을 때만 맨 위로 올린다
  for (const card of [...incoming].reverse()) {
    state.seen.add(card.concept_id);
    const old = state.cards.find((c) => c.concept_id === card.concept_id);
    if (old && JSON.stringify(old.state) === JSON.stringify(card.state)) {
      Object.assign(old, { reason: card.reason, score: card.score });
      continue;
    }
    state.cards = state.cards.filter((c) => c !== old);
    state.cards.unshift({ ...card, fresh: true, changed: Boolean(old) });
    if (old && state.active === card.concept_id) showRefresh(card);
  }
  state.cards = state.cards.slice(0, MAX_CARDS);
  renderCards();
}

function showRefresh(card) {
  const btn = $("#viz-refresh");
  btn.hidden = false;
  btn.onclick = () => openCard(state.cards.find((c) => c.concept_id === card.concept_id));
}

function renderCards() {
  const list = $("#cards");
  list.innerHTML = "";
  $("#cards-empty").hidden = state.cards.length > 0;
  for (const card of state.cards) {
    const li = document.createElement("li");
    li.className = `card ${card.fresh ? "fresh" : ""} ${state.active === card.concept_id ? "active" : ""}`;
    li.innerHTML = `<div class="name"></div><div class="values"></div><div class="reason"></div>${card.viz ? "" : '<div class="noviz">시각화 없음 · 확인 질문</div>'}`;
    li.querySelector(".name").textContent = card.name + (card.changed ? " · 새 값" : "");
    li.querySelector(".values").textContent = summarize(card);
    li.querySelector(".reason").textContent = card.reason;
    li.addEventListener("click", () => openCard(card));
    list.append(li);
    card.fresh = false;
  }
}

function openCard(card) {
  state.active = card.concept_id;
  state.opened.add(card.concept_id);
  card.changed = false;
  $("#viz-refresh").hidden = true;
  $("#viz-empty").hidden = true;
  $("#viz-host").hidden = false;
  $("#viz-title").textContent = card.name;
  $("#viz-reason").textContent = card.reason;
  $("#viz-question").textContent = `물어볼 질문: ${card.question}`;
  const body = $("#viz-body");
  body.innerHTML = "";
  if (card.viz && VIZ[card.viz]) VIZ[card.viz].mount(body, card.state);
  else body.innerHTML = '<p class="hint">이 개념은 아직 시각화가 없습니다. 아래 질문으로 확인해 보세요.</p>';
  renderCards();
}

$("#end-btn").addEventListener("click", async () => {
  stopRecording();
  await api("/api/session/end", { learner: state.learner, concepts: [...state.seen], opened: [...state.opened] });
  state.lines = []; // 받아 적은 글도 화면에서 지운다
  $("#transcript").innerHTML = "";
  addLine("평가를 마쳤습니다. 다룬 개념만 기록했습니다.");
});

loadHealth();
