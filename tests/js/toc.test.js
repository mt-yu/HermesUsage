// tests/js/toc.test.js
import test from "node:test";
import assert from "node:assert/strict";

import { pickActive } from "../../web/assets/lib/toc.js";

const OFFSETS = [
  { id: "s1", top: 0 },
  { id: "s2", top: 600 },
  { id: "s3", top: 1200 },
];

test("滚动到两个标题之间时高亮上一个", () => {
  assert.equal(pickActive(OFFSETS, 700, 90), "s2");
  assert.equal(pickActive(OFFSETS, 100, 90), "s1");
});

test("页面顶部之前仍然高亮第一个", () => {
  assert.equal(pickActive(OFFSETS, -500, 90), "s1");
});

test("滚到底部时高亮最后一个", () => {
  assert.equal(pickActive(OFFSETS, 99999, 90), "s3");
});

test("没有标题时返回 null", () => {
  assert.equal(pickActive([], 0, 90), null);
});
