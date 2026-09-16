// tests/js/keynav.test.js —— 键盘导航的纯规则。
//
// 这里只测「该不该动、往哪动」：真正的 location.href 跳转与 DOM 焦点由
// app.js 负责，浏览器里才验得了。把判定抽成纯函数的意义就在于——
// 「焦点在输入框里按 ← 不该翻页」这种最容易写错的边界，能在 Node 里断言。
import test from "node:test";
import assert from "node:assert/strict";

import { arrowTarget, cycleIndex } from "../../web/assets/lib/keynav.js";

test("ArrowLeft：有上一课 → prev", () => {
  assert.equal(arrowTarget("ArrowLeft", { hasPrev: true }), "prev");
  assert.equal(arrowTarget("ArrowLeft", { hasPrev: true, hasNext: true }), "prev");
});

test("ArrowLeft：没有上一课（第一课的空 span）→ null", () => {
  assert.equal(arrowTarget("ArrowLeft", { hasPrev: false, hasNext: true }), null);
  assert.equal(arrowTarget("ArrowLeft"), null, "不传选项时不该有方向");
});

test("ArrowRight：有下一课 → next；没有 → null", () => {
  assert.equal(arrowTarget("ArrowRight", { hasNext: true }), "next");
  assert.equal(arrowTarget("ArrowRight", { hasPrev: true, hasNext: true }), "next");
  assert.equal(arrowTarget("ArrowRight", { hasNext: false, hasPrev: true }), null);
  assert.equal(arrowTarget("ArrowRight"), null);
});

test("焦点在输入框（typing）时一律 null —— 方向键要留给光标", () => {
  for (const key of ["ArrowLeft", "ArrowRight"]) {
    assert.equal(arrowTarget(key, { typing: true, hasPrev: true, hasNext: true }), null, key);
  }
});

test("搜索面板打开（inPalette）时一律 null —— 那里的 ↑↓ 是面板自己的", () => {
  for (const key of ["ArrowLeft", "ArrowRight"]) {
    assert.equal(arrowTarget(key, { inPalette: true, hasPrev: true, hasNext: true }), null, key);
  }
  assert.equal(
    arrowTarget("ArrowLeft", { typing: true, inPalette: true, hasPrev: true, hasNext: true }),
    null,
  );
});

test("其他键不归它管：null", () => {
  for (const key of ["a", "Enter", "Tab", "ArrowUp", "ArrowDown", " ", "Left", ""]) {
    assert.equal(arrowTarget(key, { hasPrev: true, hasNext: true }), null, JSON.stringify(key));
  }
  assert.equal(arrowTarget(undefined, { hasPrev: true, hasNext: true }), null);
});

test("cycleIndex：首尾环绕", () => {
  assert.equal(cycleIndex(0, 1, 3), 1);
  assert.equal(cycleIndex(1, 1, 3), 2);
  assert.equal(cycleIndex(2, 1, 3), 0, "最后一项再往下回到第一项");
  assert.equal(cycleIndex(-1, 1, 3), 0, "从头往回一步绕到末尾");
  assert.equal(cycleIndex(0, -1, 3), 2, "第一项再往上绕到末尾");
  assert.equal(cycleIndex(1, -1, 5), 0);
});

test("cycleIndex：长度为 0 也是合法输入，返回 0", () => {
  assert.equal(cycleIndex(0, 1, 0), 0);
  assert.equal(cycleIndex(3, -1, 0), 0);
  assert.equal(cycleIndex(0, 1, -2), 0, "负长度按空列表处理");
});

test("cycleIndex：非法数字也给得回合法的索引", () => {
  for (const [current, delta, length] of [
    [NaN, 1, 3],
    [undefined, 1, 3],
    ["2", -1, 3],
    [1.7, 0, 3],
    [0, NaN, 3],
    [0, 1, NaN],
    [Infinity, 1, 3],
  ]) {
    const got = cycleIndex(current, delta, length);
    assert.ok(Number.isInteger(got), `${current}/${delta}/${length} → ${got} 不是整数`);
    assert.ok(got >= 0 && got < 3, `${current}/${delta}/${length} → ${got} 越界`);
  }
  assert.equal(cycleIndex(NaN, 1, 3), 1, "非法 current 视作 0（列表开头），delta 照常生效");
  assert.equal(cycleIndex(NaN, 0, 3), 0);
  assert.equal(cycleIndex("2", 1, 3), 0, "能整体转成数字的字符串按数字处理：2 + 1 → 绕回 0");
  assert.equal(cycleIndex(0, 1, 4.9), 1, "小数长度向下取整");
});

test("cycleIndex：delta 走满一圈回到原处", () => {
  let idx = 1;
  for (let i = 0; i < 3; i += 1) idx = cycleIndex(idx, 1, 3);
  assert.equal(idx, 1);
});
