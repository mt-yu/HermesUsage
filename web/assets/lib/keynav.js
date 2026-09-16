// web/assets/lib/keynav.js —— 键盘导航的纯判定。
//
// 为什么单独一个文件
// ------------------
// 「←/→ 翻到上一课/下一课」看着只是一次 location.href，但真正会出错的是
// **什么时候不该翻**：焦点在搜索框里按 ← 是把光标左移，不是翻课；搜索面板
// 打开时方向键归面板自己的 ↑↓；第一课的左箭头位置是空 <span>，没有目标。
// 这些判定塞进 DOM 事件里就只能靠人肉在浏览器里点，抽成纯函数后
// node --test 能直接断言（见 tests/js/keynav.test.js）。

/**
 * 方向键该翻向哪一课。
 *
 * @param {string} key         KeyboardEvent.key
 * @param {{typing?: boolean, inPalette?: boolean, hasPrev?: boolean, hasNext?: boolean}} opts
 *   typing    焦点在 input/textarea/select/contenteditable 里
 *   inPalette 搜索面板正打开（那里的方向键是面板自己在用）
 *   hasPrev / hasNext 页面里真的有上一课 / 下一课的链接
 * @returns {"prev"|"next"|null}
 */
export function arrowTarget(key, { typing = false, inPalette = false, hasPrev = false, hasNext = false } = {}) {
  if (typing || inPalette) return null;
  if (key === "ArrowLeft") return hasPrev ? "prev" : null;
  if (key === "ArrowRight") return hasNext ? "next" : null;
  return null;
}

/**
 * 高亮游标移动一格，环绕。
 *
 * 环绕是返回值自己保证的，调用方不需要再夹一次：`-1` 与越界的输入都会
 * 落到 `[0, length)` 里，所以「从第一项往上」和「从最后一项往下」都不会
 * 得到负索引或 undefined（那会让 render() 找不到高亮项，键盘就卡死了）。
 * 非法输入（NaN / 字符串 / 小数）按「当作 0 / 取整」处理 —— 没有长度的
 * 列表返回 0，非法 current 视作列表开头、delta 照常生效；非法 delta 视作
 * 原地不动。结果一定是合法索引，绝不抛异常。
 *
 * @param {number} current 当前高亮下标
 * @param {number} delta   +1 下一个 / -1 上一个
 * @param {number} length  列表长度（0 = 空列表）
 * @returns {number} 合法下标
 */
export function cycleIndex(current, delta, length) {
  const size = toInt(length);
  if (!(size > 0)) return 0;
  const step = toInt(delta) || 0;
  const from = toInt(current) || 0;
  return (((from + step) % size) + size) % size;
}

/* 只有真正是数字（或能整体转成数字的字符串，如 "2"）才取整，其余一律 0：
   `Math.trunc("abc")` 是 NaN，而 NaN 会一路污染到下标。 */
function toInt(value) {
  const n = Number(value);
  return Number.isFinite(n) ? Math.trunc(n) : 0;
}
