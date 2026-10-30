// LRU 캐시(이중 연결 리스트 + 해시맵). 시작 상태: { capacity, ops: [{op, key}], stop_at }
// 연산을 하나씩 실행하며 리스트 순서와 해시맵이 어떻게 바뀌는지 보여 준다.

export function mount(el, state) {
  const capacity = state.capacity;
  const ops = state.ops.map((o) => ({ ...o }));
  let step = state.stop_at ?? ops.length;

  el.innerHTML = `
    <div class="controls">
      <button data-act="prev" class="secondary">◀ 이전</button>
      <button data-act="next" class="secondary">다음 ▶</button>
      <input data-in="key" type="text" maxlength="2" placeholder="키">
      <button data-act="put">넣기</button>
      <button data-act="get" class="secondary">조회</button>
      <span class="step"></span>
    </div>
    <div class="lru-ops"></div>
    <div class="explain"></div>
    <div class="lru-end">최근 사용(MRU) ←</div>
    <div class="lru-list"></div>
    <div class="lru-end" style="text-align:right">→ 가장 오래됨(LRU), 다음에 밀려남</div>
    <table class="lru-map"><thead><tr><th>해시맵 키</th><th>가리키는 노드</th></tr></thead><tbody></tbody></table>`;
  const $ = (s) => el.querySelector(s);

  el.addEventListener("click", (e) => {
    const act = e.target.dataset.act;
    if (!act) return;
    const key = $("[data-in=key]").value.trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
    if (act === "prev") step = Math.max(0, step - 1);
    if (act === "next") step = Math.min(ops.length, step + 1);
    if ((act === "put" || act === "get") && key) {
      ops.splice(step); // 되감은 뒤 새 연산을 하면 그 뒤 기록은 버린다
      ops.push({ op: act, key });
      step = ops.length;
    }
    render();
  });

  function run(n) {
    let list = []; // 앞이 MRU
    let event = null;
    for (let i = 0; i < n; i++) {
      const { op, key } = ops[i];
      const at = list.indexOf(key);
      event = { op, key, hit: at !== -1, evicted: null };
      if (at !== -1) list.splice(at, 1);
      if (op === "get" && at === -1) continue; // 없는 키 조회는 순서를 바꾸지 않는다
      list.unshift(key);
      if (list.length > capacity) event.evicted = list.pop();
    }
    return { list, event };
  }

  function render() {
    const { list, event } = run(step);
    $(".lru-ops").innerHTML = ops.map((o, i) =>
      `<span class="op ${i < step ? "done" : ""} ${i === step - 1 ? "current" : ""}">${o.op === "put" ? "넣기" : "조회"} ${o.key}</span>`
    ).join("");
    const nodes = list.map((k) => `<span class="node ${event && k === event.key ? "new" : ""}">${k}</span>`);
    if (event?.evicted) nodes.push(`<span class="node evict">${event.evicted}</span>`);
    $(".lru-list").innerHTML = nodes.join('<span class="arrow">⇄</span>') || '<span class="hint">비어 있음</span>';
    $(".lru-map tbody").innerHTML = list.map((k) => `<tr><td>${k}</td><td>노드 ${k}</td></tr>`).join("");
    $(".step").textContent = `${step} / ${ops.length} 연산 · 용량 ${capacity}`;
    $(".explain").textContent = explain(event, list) + nextHint(list);
  }

  function nextHint(list) {
    // 다음 연산이 교체를 일으키면 결과를 보기 전에 먼저 생각해 보게 한다
    const next = ops[step];
    if (!next || list.includes(next.key) || next.op === "get" || list.length < capacity) return "";
    return ` 다음은 '넣기 ${next.key}'. 누가 밀려날까요?`;
  }

  function explain(ev, list) {
    if (!ev) return "아직 실행한 연산이 없습니다. 다음 ▶을 누르세요.";
    if (ev.op === "get" && !ev.hit) return `${ev.key}는 해시맵에 없어 조회 실패. 순서는 그대로입니다.`;
    if (ev.op === "get") return `${ev.key}를 해시맵으로 바로 찾고(O(1)), 리스트 맨 앞으로 옮깁니다. 조회만 해도 순서가 바뀝니다.`;
    if (ev.evicted) return `${ev.key}를 맨 앞에 넣자 용량 ${capacity}을 넘어, 맨 뒤의 ${ev.evicted}가 밀려났습니다. 해시맵에서도 지웁니다.`;
    if (ev.hit) return `${ev.key}는 이미 있어 값을 바꾸고 맨 앞으로 옮깁니다.`;
    return `${ev.key}를 맨 앞에 넣습니다. (${list.length}/${capacity})`;
  }

  render();
}
