// 추천 카드에 붙이는 짧은 설명. 평가 화면과 비교 화면이 함께 쓴다.

export const LEVEL_LABEL = { basic: "기본 단계", tricky: "헷갈리기 쉬운 단계", advanced: "어려운 상황" };
export const STATUS_LABEL = { new: "새로 앎", confused: "헷갈림", familiar: "익숙함" };

export function summarize(card) {
  const s = card.state;
  if (!s) return "";
  if (card.viz === "hash") return `키 ${s.keys.join(", ")} · ${s.size}칸`;
  if (card.viz === "lru") return `용량 ${s.capacity} · ${s.ops.map((o) => (o.op === "get" ? "조회 " : "") + o.key).join(" → ")}`;
  return "";
}
