// tests/js/storage.test.js
import test from "node:test";
import assert from "node:assert/strict";

import {
  loadState, saveState, parseState, STORAGE_KEY,
  EXERCISE_KEY, loadExercises, saveExercises, parseExercises,
} from "../../web/assets/lib/storage.js";

function fakeStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    _map: map,
  };
}

test("loadState 在没有数据时返回空状态", () => {
  assert.deepEqual(loadState(fakeStorage()), { version: 1, done: {} });
});

test("saveState 之后 loadState 能读回", () => {
  const s = fakeStorage();
  saveState({ version: 1, done: { L00: { at: "x", note: "" } } }, s);
  assert.equal(s._map.has(STORAGE_KEY), true);
  assert.equal(loadState(s).done.L00.at, "x");
});

test("loadState 容忍坏 JSON（浏览器存储被手改过）", () => {
  assert.deepEqual(loadState(fakeStorage({ [STORAGE_KEY]: "{不是 json" })), { version: 1, done: {} });
});

test("loadState 在 storage 抛错时也不崩（隐私模式）", () => {
  const throwing = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
  assert.deepEqual(loadState(throwing), { version: 1, done: {} });
  assert.equal(saveState({ version: 1, done: {} }, throwing), false);
});

test("parseState 接受合法状态并统计导入课数", () => {
  const r = parseState('{"done": {"L00": {"at": "2026-09-16T10:00:00", "note": "跑通了"}}}');
  assert.equal(r.ok, true);
  assert.equal(r.imported, 1);
  assert.equal(r.state.done.L00.note, "跑通了");
});

test("parseState 拒绝非对象与坏 JSON", () => {
  assert.equal(parseState("[]").ok, false);
  assert.equal(parseState("not json").ok, false);
  assert.equal(parseState('{"done": "L00"}').ok, false);
});

test("parseState 丢弃非法课号", () => {
  const r = parseState('{"done": {"L00": {}, "javascript": {}, "L01": {}}}');
  assert.deepEqual(Object.keys(r.state.done).sort(), ["L00", "L01"]);
});

test("练习用独立键：与课程进度互不覆盖", () => {
  const s = fakeStorage();
  saveExercises({ version: 1, lessons: { L15: { 1: { at: "t" } } } }, s);
  saveState({ version: 1, done: { L15: { at: "x", note: "" } } }, s);
  assert.notEqual(EXERCISE_KEY, STORAGE_KEY);
  assert.equal(s._map.has(EXERCISE_KEY), true, "练习状态必须落在自己的键上");
  assert.equal(s._map.has(STORAGE_KEY), true, "课程进度不能被练习覆盖");
  assert.equal(loadExercises(s).lessons.L15["1"].at, "t");
  assert.equal(loadState(s).done.L15.at, "x");
});

test("saveExercises 之后 loadExercises 能读回", () => {
  const s = fakeStorage();
  assert.equal(saveExercises({ version: 1, lessons: { L15: { 1: { at: "2026-09-16T07:00:00Z" }, 3: { at: "2026-09-16T07:05:00Z" } } } }, s), true);
  const back = loadExercises(s);
  assert.deepEqual(Object.keys(back.lessons.L15).sort(), ["1", "3"]);
  assert.equal(back.lessons.L15["3"].at, "2026-09-16T07:05:00Z");
});

test("loadExercises 在没有数据或坏 JSON 时返回空结构", () => {
  assert.deepEqual(loadExercises(fakeStorage()), { version: 1, lessons: {} });
  assert.deepEqual(loadExercises(fakeStorage({ [EXERCISE_KEY]: "{坏掉的 json" })), { version: 1, lessons: {} });
  assert.deepEqual(loadExercises(fakeStorage({ [EXERCISE_KEY]: '"字符串"' })), { version: 1, lessons: {} });
});

test("loadExercises 在 storage 抛错时也不崩（隐私模式）", () => {
  const throwing = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
  assert.deepEqual(loadExercises(throwing), { version: 1, lessons: {} });
  assert.equal(saveExercises({ version: 1, lessons: {} }, throwing), false);
});

test("parseExercises 接受合法状态并统计导入题目数", () => {
  const r = parseExercises('{"version":1,"lessons":{"L15":{"1":{"at":"2026-09-16T07:00:00Z"},"3":{"at":"x"}},"L16":{"2":{"at":""}}}}');
  assert.equal(r.ok, true);
  assert.equal(r.imported, 3);
  assert.deepEqual(Object.keys(r.state.lessons).sort(), ["L15", "L16"]);
  assert.equal(r.state.lessons.L15["1"].at, "2026-09-16T07:00:00Z");
});

test("parseExercises 静默丢弃非法课号与练习号", () => {
  const r = parseExercises('{"lessons":{"L15":{"1":{"at":"x"},"abc":{"at":"x"},"2.5":{"at":"x"}},"javascript":{"1":{"at":"x"}},"L1":{"9":{"at":"x"}},"L16":"不是对象"}}');
  assert.equal(r.ok, true);
  assert.deepEqual(Object.keys(r.state.lessons), ["L15"]);
  assert.deepEqual(Object.keys(r.state.lessons.L15), ["1"]);
  assert.equal(r.imported, 1, "imported 只数清洗后留下的题目");
});

test("parseExercises：at 不是字符串时补空串", () => {
  const r = parseExercises('{"lessons":{"L15":{"1":{"at":123},"2":null,"3":{"at":"x"}}}}');
  assert.equal(r.ok, true);
  assert.equal(r.imported, 3);
  assert.equal(r.state.lessons.L15["1"].at, "");
  assert.equal(r.state.lessons.L15["2"].at, "");
  assert.equal(r.state.lessons.L15["3"].at, "x");
});

test("parseExercises 拒绝坏 JSON、非对象顶层与非法 lessons", () => {
  assert.equal(parseExercises("not json").ok, false);
  assert.equal(parseExercises("[]").ok, false);
  assert.equal(parseExercises('"L15"').ok, false);
  assert.equal(parseExercises('{"lessons": "L15"}').ok, false);
  assert.equal(parseExercises('{"lessons": []}').ok, false);
  assert.equal(parseExercises('{"version": 1}').ok, true, "缺 lessons 视为空，与 parseState 一致");
});

test("mimeFor 按扩展名推断类型（.md 报告不该写成 JSON）", async () => {
  const { mimeFor } = await import("../../web/assets/lib/storage.js");
  assert.equal(mimeFor("hermes-usage-report.md"), "text/markdown;charset=utf-8");
  assert.equal(mimeFor("progress.state.json"), "application/json;charset=utf-8");
  assert.equal(mimeFor("notes.txt"), "text/plain;charset=utf-8");
  assert.equal(mimeFor("unknown"), "application/json;charset=utf-8");
});
