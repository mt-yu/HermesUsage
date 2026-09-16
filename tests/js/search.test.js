// tests/js/search.test.js
import test from "node:test";
import assert from "node:assert/strict";

import { tokenize, search, snippet } from "../../web/assets/lib/search.js";

test("tokenize 把中文切成二字片段", () => {
  assert.deepEqual(tokenize("技能系统"), ["技能", "能系", "系统"]);
});

test("tokenize 保留英文单词并小写化", () => {
  // 计划里这条写的是 ["skills", "记忆"]，但计划给出的 tokenize 实现会把
  // 单字中文（与）也保留下来（另一条测试「单字中文与数字也保留」正是这个意思），
  // 两者互相矛盾。以实现的真实行为为准，并把偏差写在这里。
  assert.deepEqual(tokenize("Skills 与 记忆"), ["skills", "与", "记忆"]);
});

test("tokenize 单字中文与数字也保留", () => {
  assert.deepEqual(tokenize("看 L15 课"), ["看", "l15", "课"]);
});

test("tokenize 去重", () => {
  assert.deepEqual(tokenize("技能 技能"), ["技能"]);
});

const INDEX = {
  docs: [
    { id: "L15", title: "技能系统：让它学会你的活法", stage: 1, summary: "技能是按需加载的说明书",
      text: "技能放在 ~/.hermes/skills/ 下，项目级技能需要 hermes skills trust .",
      tokens: "技能 能系 系统 技能 放在 skills 项目 目级 级技 技能 需要 hermes skills trust" },
    { id: "L23", title: "定时与循环", stage: 2, summary: "cron 与 loops",
      text: "hermes cron list 看作业，hermes cron resume 启用",
      tokens: "定时 时与 与循 循环 cron 与 loops hermes cron list 看作 作业 hermes cron resume 启用" },
  ],
};

test("search 命中全文里的关键词", () => {
  const hits = search(INDEX, "cron");
  assert.equal(hits.length, 1);
  assert.equal(hits[0].id, "L23");
});

test("search 中文按二字片段命中", () => {
  const hits = search(INDEX, "项目技能");
  assert.equal(hits[0].id, "L15");
});

test("search 标题命中排在正文命中前面", () => {
  const hits = search(INDEX, "技能");
  assert.equal(hits[0].id, "L15");
});

test("search 无关键词或匹配不上时返回空数组", () => {
  assert.deepEqual(search(INDEX, ""), []);
  assert.deepEqual(search(INDEX, "zzzz"), []);
});

test("snippet 截取命中附近文本", () => {
  const doc = INDEX.docs[1];
  const s = snippet(doc, ["resume"], 20);
  assert.ok(s.includes("resume"), s);
  assert.ok(s.startsWith("…") || s.length >= 10);
});

test("tokenizeToQuery 输出可被 search 直接消费的片段串", async () => {
  const { tokenizeToQuery } = await import("../../web/assets/lib/search.js");
  assert.equal(tokenizeToQuery("技能系统"), "技能 能系 系统");
});
