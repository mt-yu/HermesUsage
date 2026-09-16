// web/assets/lib/util.js —— 无依赖的小工具。纯函数，方便 node --test 直接跑。

export function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

export function formatMinutes(min) {
  const n = Number(min) || 0;
  if (n < 60) return `${n} 分钟`;
  return `${Math.floor(n / 60)} 小时 ${n % 60} 分钟`;
}

export function clamp(n, lo, hi) {
  return Math.min(hi, Math.max(lo, n));
}

export function debounce(fn, ms = 120) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

/* 只挑「真正代表一课」的元素。
   `<body data-lesson="…">` 也带这个属性：不过滤的话，它的 querySelector('.nav-check')
   会命中侧栏第一课的圆圈，于是点 L00 会连带写进一条 ""（首页）或 L15（课程页）的幽灵记录。 */
export function lessonItems(nodes) {
  return [...nodes].filter((node) => node && node.dataset && node.dataset.lesson);
}
