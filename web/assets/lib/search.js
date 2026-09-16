// web/assets/lib/search.js —— 纯前端全文检索。
//
// 为什么不用 lunr/Fuse.js：本仓库刻意不引入 npm 依赖与打包器，
// 而这里的语料只有 32 课（约 450KB），一个 60 行的评分函数足够，
// 而且它是纯函数，能被 node --test 直接覆盖。
//
// 中文处理：不引词典，直接按「二字片段」切分（用「项目技能」能命中
// 「项目级技能」这种真实场景），英文按单词切。

const CJK = /[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]/;

export function tokenize(text) {
  const out = [];
  for (const chunk of String(text || "").toLowerCase().split(/[^\p{L}\p{N}]+/u)) {
    if (!chunk) continue;
    if (!CJK.test(chunk) || chunk.length === 1) { out.push(chunk); continue; }
    for (let i = 0; i < chunk.length - 1; i++) out.push(chunk.slice(i, i + 2));
  }
  return [...new Set(out)];
}

export function search(index, query, limit = 20) {
  const terms = tokenize(query);
  if (!terms.length) return [];
  const results = [];
  for (const doc of index.docs || []) {
    const head = `${doc.title || ""} ${(doc.tags || []).join(" ")} ${doc.summary || ""}`.toLowerCase();
    const body = String(doc.tokens || "").toLowerCase();
    let score = 0;
    for (const term of terms) {
      if (head.includes(term)) score += 8;
      const freq = body.split(term).length - 1;
      if (freq > 0) score += Math.min(freq, 5);
    }
    if (score > 0) {
      results.push({ id: doc.id, title: doc.title, url: doc.url, stage: doc.stage, score, snippet: snippet(doc, terms) });
    }
  }
  return results.sort((a, b) => b.score - a.score || String(a.id).localeCompare(String(b.id))).slice(0, limit);
}

export function snippet(doc, terms, width = 80) {
  const text = doc.text || doc.summary || "";
  let at = -1;
  for (const term of terms) {
    const i = text.toLowerCase().indexOf(term);
    if (i >= 0 && (at < 0 || i < at)) at = i;
  }
  if (at < 0) return text.slice(0, width) + (text.length > width ? "…" : "");
  const start = Math.max(0, at - Math.floor(width / 3));
  return (start > 0 ? "…" : "") + text.slice(start, start + width) + (start + width < text.length ? "…" : "");
}

export function tokenizeToQuery(text) {
  return tokenize(text).join(" ");
}
