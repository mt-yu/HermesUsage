// tests/js/util.test.js —— 跑法：node --test tests/js
import test from "node:test";
import assert from "node:assert/strict";

import { escapeHtml, formatMinutes, clamp } from "../../web/assets/lib/util.js";

test("escapeHtml 转义五个字符", () => {
  assert.equal(escapeHtml(`<a href="x">&'</a>`), "&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;");
});

test("escapeHtml 对非字符串输入也安全", () => {
  assert.equal(escapeHtml(42), "42");
  assert.equal(escapeHtml(null), "null");
});

test("formatMinutes 超过 60 分钟换成小时", () => {
  assert.equal(formatMinutes(45), "45 分钟");
  assert.equal(formatMinutes(60), "1 小时 0 分钟");
  assert.equal(formatMinutes(135), "2 小时 15 分钟");
});

test("clamp 夹在区间内", () => {
  assert.equal(clamp(5, 0, 3), 3);
  assert.equal(clamp(-1, 0, 3), 0);
  assert.equal(clamp(2, 0, 3), 2);
});

test("lessonItems 丢掉没有课号的节点（body[data-lesson=''] 是真实存在的坑）", async () => {
  const { lessonItems } = await import("../../web/assets/lib/util.js");
  const nodes = [
    { dataset: { lesson: "L00" } },
    { dataset: { lesson: "" } },
    { dataset: {} },
    { dataset: { lesson: "L15" } },
  ];
  assert.deepEqual(lessonItems(nodes).map((n) => n.dataset.lesson), ["L00", "L15"]);
});
