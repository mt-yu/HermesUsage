// tests/js/storage.test.js
import test from "node:test";
import assert from "node:assert/strict";

import { loadState, saveState, parseState, STORAGE_KEY } from "../../web/assets/lib/storage.js";

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
