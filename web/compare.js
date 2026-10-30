// 같은 대화를 피드백이 다른 두 학습자에게 넣고, 추천 순서와 시작 상태가 어떻게 갈리는지 나란히 보여 준다.
import * as hashViz from "./viz/hash.js";
import * as lruViz from "./viz/lru.js";
import { LEVEL_LABEL, STATUS_LABEL, summarize } from "./summary.js";

const VIZ = { hash: hashViz, lru: lruViz };
const WINDOW = 3;
const SIDES = ["a", "b"];
const NAMES = { a: "A", b: "B" };

const $ = (s, root = document) => root.querySelector(s);
const state = { lines: [], statuses: { a: {}, b: {} }, conceptNames: {} };

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
    $(".viz-body", col).innerHTML = '<p class="hint">대화에 맞는 시각화가 없습니다.</p>';
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

async function say(text) {
  state.lines.push(text);
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

$("#reset").addEventListener("click", () => {
  state.lines = [];
  $("#talk-log").innerHTML = "";
  $("#diff").hidden = true;
  SIDES.forEach((side) => {
    const col = $(`.side[data-side=${side}]`);
    $(".rank", col).innerHTML = "";
    $(".viz-title", col).textContent = "";
    $(".viz-body", col).innerHTML = "";
  });
});

for (const side of SIDES) {
  $(`.learner[data-side=${side}] textarea`).addEventListener("change", async () => {
    await analyzeFeedback(side);
    if (state.lines.length) await recommendBoth();
  });
}

(async () => {
  const h = await (await fetch("/api/health")).json();
  state.conceptNames = h.concepts;
  await Promise.all(SIDES.map(analyzeFeedback));
})();
