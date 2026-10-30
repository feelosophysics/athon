// 체이닝 해시표. 시작 상태: { size, keys, focus, lookup }
// 키를 하나씩 넣는 단계를 되감거나 넘겨 볼 수 있고, 키를 더 넣거나 찾아볼 수 있다.

export function mount(el, state) {
  let size = state.size;
  let keys = [...state.keys];
  let lookup = state.lookup;
  let step = initialStep(state);

  el.innerHTML = `
    <div class="controls">
      <button data-act="prev" class="secondary">◀ 이전</button>
      <button data-act="next" class="secondary">다음 ▶</button>
      <input data-in="key" type="number" placeholder="키">
      <button data-act="add">넣기</button>
      <button data-act="find" class="secondary">찾기</button>
      <span class="step"></span>
    </div>
    <div class="explain"></div>
    <div class="buckets"></div>`;
  const $ = (s) => el.querySelector(s);

  el.addEventListener("click", (e) => {
    const act = e.target.dataset.act;
    if (!act) return;
    const v = parseInt($("[data-in=key]").value, 10);
    if (act === "prev") step = Math.max(0, step - 1);
    if (act === "next") step = Math.min(keys.length, step + 1);
    if (act === "add" && Number.isInteger(v) && v >= 0) { keys.push(v); step = keys.length; lookup = null; }
    if (act === "find" && Number.isInteger(v)) { lookup = v; step = keys.length; }
    render();
  });

  function render() {
    const table = Array.from({ length: size }, () => []);
    keys.slice(0, step).forEach((k) => table[k % size].push(k));
    const last = step > 0 ? keys[step - 1] : null;
    const lastSlot = last === null ? -1 : last % size;
    const collided = last !== null && table[lastSlot].length > 1;
    const showLookup = lookup !== null && lookup !== undefined && step === keys.length;
    const lookSlot = showLookup ? lookup % size : -1;

    $(".buckets").innerHTML = table.map((chain, i) => {
      const nodes = chain.map((k, j) => {
        let cls = "";
        if (showLookup && i === lookSlot) {
          const pos = chain.indexOf(lookup);
          cls = j === pos ? "found" : (pos === -1 || j < pos ? "visit" : "");
        } else if (k === last && j === chain.length - 1) {
          cls = collided ? "collide" : "new";
        }
        return `<span class="node ${cls}">${k}</span>`;
      }).join('<span class="arrow">→</span>');
      const hit = i === lastSlot || i === lookSlot;
      return `<div class="bucket ${hit ? "hit" : ""}"><span class="idx">${i}</span><span class="slot"></span>${nodes}</div>`;
    }).join("");

    $(".step").textContent = `${step} / ${keys.length}개 넣음 · 칸 ${size}개 · 적재율 ${(step / size).toFixed(2)}`;
    $(".explain").textContent = explain(table, last, collided, showLookup);
  }

  function explain(table, last, collided, showLookup) {
    if (showLookup) {
      const chain = table[lookup % size];
      const pos = chain.indexOf(lookup);
      const compares = pos === -1 ? chain.length : pos + 1;
      return pos === -1
        ? `${lookup} % ${size} = ${lookup % size}번 칸을 끝까지 ${compares}번 비교했지만 없습니다.`
        : `${lookup} % ${size} = ${lookup % size}번 칸에서 ${compares}번 비교해 찾았습니다. 체인이 길수록 비교가 늘어납니다.`;
    }
    if (last === null) return "아직 넣은 키가 없습니다. 다음 ▶을 누르세요.";
    const slot = last % size;
    if (collided) return `${last} % ${size} = ${slot}. 이미 ${table[slot].length - 1}개가 있는 칸이라 충돌! 체인 끝에 이어 붙입니다.`;
    return `${last} % ${size} = ${slot}번 칸에 넣습니다.`;
  }

  render();
}

function initialStep(state) {
  // collision이면 처음 충돌이 나는 순간에서 멈춘다. 나머지는 끝까지 넣은 상태로 연다
  if (state.focus !== "collision") return state.keys.length;
  const seen = new Set();
  for (let i = 0; i < state.keys.length; i++) {
    const slot = state.keys[i] % state.size;
    if (seen.has(slot)) return i + 1;
    seen.add(slot);
  }
  return state.keys.length;
}
