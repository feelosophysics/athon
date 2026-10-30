// 같은 대화를 피드백이 다른 두 학습자에게 넣고, 추천 순서와 시작 상태가 어떻게 갈리는지 나란히 보여 준다.
import * as hashViz from "./viz/hash.js";
import * as lruViz from "./viz/lru.js";
import { LEVEL_LABEL, STATUS_LABEL, summarize } from "./summary.js";

const VIZ = { hash: hashViz, lru: lruViz };
const WINDOW = 3;
const SIDES = ["a", "b"];
const EXAMPLES = [
  "해시표에 5, 15, 25 넣고 25를 찾으면 몇 번 비교해?",
  "버킷이 7개인 해시 테이블에 10이랑 17을 넣으면 충돌 나지?",
  "lru 캐시에 a, b 넣고 a 조회하고 c 넣으면 크기 2니까 b가 빠지지?",
  "TTL 만료 시간을 힙으로 관리하면",
  "브랜치 만들면 커밋을 가리키는 포인터만 생기는 거지?",
];
const EMPTY_START = '<p class="empty-note">대본 <b>①</b>을 누르면 여기에 추천이 뜹니다.</p>';
const EMPTY_MISS = `<p class="empty-note">최근 대화에서 아는 개념을 찾지 못했습니다. 이런 말을 넣어 보세요:<br>“${EXAMPLES[0]}”</p>`;

const $ = (s, root = document) => root.querySelector(s);
const state = { lines: [], statuses: { a: {}, b: {} }, conceptNames: {}, exampleAt: 0 };

async function post(path, body) {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json();
}

async function analyzeFeedback(side) {
  const panel = $(`.learner[data-side=${side}]`);
  const feedback = $("textarea", panel).value.trim();
  const box = $(".statuses", panel);
  box.innerHTML = "";
  if (!feedback) {
    state.statuses[side] = {};
    return;
  }
  const p = await post("/api/profile", { learner: `compare-${side}`, feedback, save: false });
  state.statuses[side] = p.statuses;
  for (const f of p.findings) {
    const chip = document.createElement("span");
    chip.className = `chip ${f.status}`;
    chip.textContent = `${state.conceptNames[f.concept_id] ?? f.concept_id} · ${STATUS_LABEL[f.status]}`;
    chip.title = f.evidence;
    box.append(chip);
  }
}

async function recommendBoth() {
  const lines = state.lines.slice(-WINDOW);
  const results = await Promise.all(
    SIDES.map((side) => post("/api/analyze", { learner: `compare-${side}`, lines, statuses: state.statuses[side] }))
  );
  const cards = Object.fromEntries(SIDES.map((side, i) => [side, results[i].cards]));
  SIDES.forEach((side) => renderSide(side, cards[side]));
  renderDiff(cards);
}

function renderSide(side, cards) {
  const col = $(`.side[data-side=${side}]`);
  const rank = $(".rank", col);
  rank.innerHTML = "";
  cards.forEach((card, i) => {
    const li = document.createElement("li");
    li.className = `card ${i === 0 ? "active" : ""}`;
    li.innerHTML = '<div class="name"></div><div class="values"></div><div class="reason"></div>';
    $(".name", li).textContent = `${i + 1}. ${card.name}`;
    $(".values", li).textContent = [summarize(card), card.viz ? LEVEL_LABEL[card.level] + "부터" : "확인 질문"].filter(Boolean).join(" · ");
    $(".reason", li).textContent = card.reason;
    li.addEventListener("click", () => openViz(col, card));
    rank.append(li);
  });
  const top = cards.find((c) => c.viz);
  if (top) openViz(col, top);
  else {
    $(".viz-title", col).textContent = "";
    $(".viz-body", col).innerHTML = cards.length
      ? '<p class="hint">이 개념은 아직 시각화가 없습니다. 카드의 확인 질문으로 이야기해 보세요.</p>'
      : EMPTY_MISS;
  }
}

function openViz(col, card) {
  $(".viz-title", col).textContent = `${card.name} — ${LEVEL_LABEL[card.level]}부터`;
  const body = $(".viz-body", col);
  body.innerHTML = "";
  VIZ[card.viz]?.mount(body, card.state);
}

function renderDiff(cards) {
  const diff = $("#diff");
  const parts = [];
  const [a, b] = [cards.a[0], cards.b[0]];
  if (a && b && a.concept_id !== b.concept_id) {
    parts.push(`1순위가 다릅니다: A는 ${a.name}, B는 ${b.name}`);
  }
  for (const ca of cards.a) {
    const cb = cards.b.find((c) => c.concept_id === ca.concept_id);
    if (cb && ca.viz && ca.level !== cb.level) {
      parts.push(`${ca.name}: A는 ${LEVEL_LABEL[ca.level]}부터, B는 ${LEVEL_LABEL[cb.level]}부터`);
    }
  }
  diff.hidden = parts.length === 0;
  diff.textContent = parts.length ? `같은 대화, 다른 추천 — ${parts.join(" / ")}` : "";
}

function markSteps() {
  // 다음에 누를 대본 버튼을 강조한다
  const steps = [...document.querySelectorAll(".step-btn")];
  const next = steps.find((b) => !state.lines.includes(b.dataset.line));
  steps.forEach((b) => {
    b.classList.toggle("done", state.lines.includes(b.dataset.line));
    b.classList.toggle("next", b === next);
  });
}

async function say(text) {
  state.lines.push(text);
  markSteps();
  const li = document.createElement("li");
  li.textContent = text;
  $("#talk-log").append(li);
  await recommendBoth();
}

$("#say").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("#say-text").value.trim();
  if (!text) return;
  $("#say-text").value = "";
  say(text);
});

document.querySelectorAll("[data-line]").forEach((btn) => btn.addEventListener("click", () => say(btn.dataset.line)));

$("#example").addEventListener("click", () => {
  $("#say-text").value = EXAMPLES[state.exampleAt++ % EXAMPLES.length];
  $("#say-text").focus();
});

function reset() {
  state.lines = [];
  $("#talk-log").innerHTML = "";
  $("#diff").hidden = true;
  SIDES.forEach((side) => {
    const col = $(`.side[data-side=${side}]`);
    $(".rank", col).innerHTML = "";
    $(".viz-title", col).textContent = "";
    $(".viz-body", col).innerHTML = EMPTY_START;
  });
  markSteps();
}
$("#reset").addEventListener("click", reset);

for (const side of SIDES) {
  $(`.learner[data-side=${side}] textarea`).addEventListener("change", async () => {
    await analyzeFeedback(side);
    if (state.lines.length) await recommendBoth();
  });
}

(async () => {
  // 브라우저 데모는 처음에 파이썬 엔진을 불러오느라 시간이 걸린다. 그동안 버튼을 잠근다
  reset();
  const controls = document.querySelectorAll(".talk-bar button, .talk-bar input, .learner textarea");
  controls.forEach((el) => (el.disabled = true));
  document.querySelectorAll(".statuses").forEach((box) => (box.innerHTML = '<span class="hint">분석 준비 중…</span>'));
  try {
    const h = await (await fetch("/api/health")).json();
    state.conceptNames = h.concepts;
    await Promise.all(SIDES.map(analyzeFeedback));
  } finally {
    controls.forEach((el) => (el.disabled = false));
  }
})();
