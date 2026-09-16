// tests/js/progress.test.js
import test from "node:test";
import assert from "node:assert/strict";

import { emptyState, isDone, toggleDone, completion, nextLesson, blocked } from "../../web/assets/lib/progress.js";

const LESSONS = [
  { id: "L00", title: "什么是 Hermes", minutes: 10, prereq: [] },
  { id: "L01", title: "五分钟装好", minutes: 15, prereq: ["L00"] },
  { id: "L02", title: "一次对话发生了什么", minutes: 15, prereq: ["L00"] },
];

test("emptyState 与 progress/.state.json 同构", () => {
  assert.deepEqual(emptyState(), { version: 1, done: {} });
});

test("toggleDone 不可变地翻转状态", () => {
  const s0 = emptyState();
  const s1 = toggleDone(s0, "L00", "2026-09-16T10:00:00+08:00");
  assert.equal(isDone(s0, "L00"), false, "原状态不能被改");
  assert.equal(isDone(s1, "L00"), true);
  assert.equal(s1.done.L00.at, "2026-09-16T10:00:00+08:00");
  const s2 = toggleDone(s1, "L00");
  assert.equal(isDone(s2, "L00"), false);
});

test("completion 统计完成数与剩余分钟", () => {
  const state = toggleDone(emptyState(), "L00");
  const c = completion(LESSONS, state);
  assert.deepEqual(c, { finished: 1, total: 3, minutesLeft: 30, percent: 33 });
});

test("nextLesson 跳过前置未完成的课", () => {
  const state = toggleDone(emptyState(), "L00");
  assert.equal(nextLesson(LESSONS, state).id, "L01");
});

test("nextLesson 全部完成时返回 null", () => {
  let state = emptyState();
  for (const l of LESSONS) state = toggleDone(state, l.id);
  assert.equal(nextLesson(LESSONS, state), null);
});

test("blocked 列出没做完的前置", () => {
  assert.deepEqual(blocked(LESSONS[1], emptyState()), ["L00"]);
  assert.deepEqual(blocked(LESSONS[0], emptyState()), []);
});
