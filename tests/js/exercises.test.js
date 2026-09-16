// tests/js/exercises.test.js
import test from "node:test";
import assert from "node:assert/strict";

import { emptyExercises, isExerciseDone, toggleExercise, countDone } from "../../web/assets/lib/exercises.js";

test("emptyExercises 是空结构（version 1 + lessons 对象）", () => {
  assert.deepEqual(emptyExercises(), { version: 1, lessons: {} });
});

test("isExerciseDone 只认真正打过勾的题", () => {
  const s0 = emptyExercises();
  assert.equal(isExerciseDone(s0, "L15", "1"), false);
  assert.equal(isExerciseDone(s0, "L99", "1"), false);
  const s1 = toggleExercise(s0, "L15", "1", "2026-09-16T07:00:00Z");
  assert.equal(isExerciseDone(s1, "L15", "1"), true);
  assert.equal(isExerciseDone(s1, "L15", "2"), false);
  assert.equal(isExerciseDone(s1, "L16", "1"), false);
});

test("toggleExercise 不可变：原状态不被修改", () => {
  const s0 = emptyExercises();
  const s1 = toggleExercise(s0, "L15", "1", "2026-09-16T07:00:00Z");
  assert.deepEqual(s0, { version: 1, lessons: {} }, "原对象不能被改");
  assert.notEqual(s1, s0);
  assert.equal(s1.lessons.L15["1"].at, "2026-09-16T07:00:00Z");
  assert.equal(s0.lessons.L15, undefined);
});

test("toggleExercise 打勾两次等于取消（删键而不是写 false）", () => {
  const s1 = toggleExercise(emptyExercises(), "L15", "1", "2026-09-16T07:00:00Z");
  const s2 = toggleExercise(s1, "L15", "1");
  assert.equal(isExerciseDone(s2, "L15", "1"), false);
  assert.equal("L15" in s2.lessons, false, "取消后不该留下空的 lessons[lessonId]");
  assert.equal(isExerciseDone(s1, "L15", "1"), true, "取消操作不能改到上一个状态");
});

test("取消其中一题后，同课其他题还在", () => {
  let s = emptyExercises();
  s = toggleExercise(s, "L15", "1", "2026-09-16T07:00:00Z");
  s = toggleExercise(s, "L15", "3", "2026-09-16T07:01:00Z");
  s = toggleExercise(s, "L15", "1");
  assert.equal(isExerciseDone(s, "L15", "1"), false);
  assert.equal(isExerciseDone(s, "L15", "3"), true);
  assert.deepEqual(Object.keys(s.lessons.L15), ["3"]);
});

test("countDone 数的是已做题数", () => {
  assert.equal(countDone(emptyExercises(), "L15"), 0);
  assert.equal(countDone(emptyExercises(), "L99"), 0);
  let s = emptyExercises();
  s = toggleExercise(s, "L15", "1");
  s = toggleExercise(s, "L15", "2");
  s = toggleExercise(s, "L15", "3");
  s = toggleExercise(s, "L15", "3");       // 取消第 3 题
  assert.equal(countDone(s, "L15"), 2);
  assert.equal(countDone(s, "L16"), 0);
});

test("多课互不干扰，同一题号在不同课各算各的", () => {
  let s = emptyExercises();
  s = toggleExercise(s, "L15", "1", "2026-09-16T07:00:00Z");
  s = toggleExercise(s, "L16", "1", "2026-09-16T08:00:00Z");
  s = toggleExercise(s, "L16", "2", "2026-09-16T08:01:00Z");
  assert.equal(countDone(s, "L15"), 1);
  assert.equal(countDone(s, "L16"), 2);
  s = toggleExercise(s, "L16", "1");
  assert.equal(isExerciseDone(s, "L15", "1"), true);
  assert.equal(isExerciseDone(s, "L16", "1"), false);
  assert.equal(countDone(s, "L16"), 1);
});

test("缺 lessons 字段的脏状态不会让读操作崩", () => {
  assert.equal(isExerciseDone({ version: 1 }, "L15", "1"), false);
  assert.equal(isExerciseDone(null, "L15", "1"), false);
  assert.equal(countDone({ version: 1 }, "L15"), 0);
  const s = toggleExercise({ version: 1 }, "L15", "1", "2026-09-16T07:00:00Z");
  assert.equal(isExerciseDone(s, "L15", "1"), true);
});
