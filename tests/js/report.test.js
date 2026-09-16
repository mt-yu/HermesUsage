// tests/js/report.test.js
//
// 学习报告是**给读者自己留档、也可能交给别人看**的东西（贴进 issue、放进周报、
// 交给同事）。它算错的时候，错的是一句「你已完成 3/32 课」这样与事实相反的陈述，
// 而且点一下就下载了，没有任何东西拦得住。所以这里把报告的确切文本钉死：
// generatedAt 由测试给定（实现里不许 new Date()），因此输出完全可复现。
import test from "node:test";
import assert from "node:assert/strict";

import { buildReport, summarize } from "../../web/assets/lib/report.js";
import { toggleExercise, emptyExercises } from "../../web/assets/lib/exercises.js";

const AT = "2026-09-16T07:00:00.000Z";
const SITE = "https://mt-yu.github.io/HermesUsage/";

// 三个稳定用例：20+25 分钟、练习 3+2，全部在阶段 0；L15 在阶段 1。
const LESSONS = [
  { id: "L00", title: "装好 Hermes", stage: 0, stage_name: "起步", minutes: 20, exercises: 3 },
  { id: "L01", title: "第一句话", stage: 0, stage_name: "起步", minutes: 25, exercises: 2 },
  { id: "L15", title: "技能系统", stage: 1, stage_name: "扩展能力", minutes: 45, exercises: 5 },
];

const doneState = (...ids) => ({
  version: 1,
  done: Object.fromEntries(ids.map((id) => [id, { at: AT, note: "" }])),
});

const exState = (map) => ({ version: 1, lessons: map });

/** 表格里的课程行（`| Lxx | …`）：汇总结论与数据来源里也有斜杠，不能混着数。 */
const rowsOf = (md) => md.split("\n").filter((line) => /^\| L\d+ \|/.test(line));

/** 一行表格的单元格。按**未转义的**竖线切：标题里的 `\|` 是内容，不是分隔符。 */
const columnsOf = (row) => row.split(/(?<!\\)\|/).slice(1, -1).map((c) => c.trim());

/** 只看表格行里的 ✅/○：「数据来源」一节的说明文字里也提到了这两个符号。 */
const marksOf = (md, symbol) => rowsOf(md).filter((row) => columnsOf(row)[3] === symbol).length;

test("空输入不抛，仍是一份结构完整的报告", () => {
  const md = buildReport();
  assert.equal(typeof md, "string");
  assert.match(md, /^# .*学习报告\n/);
  assert.match(md, /生成时间：/);
  assert.match(md, /完成 0\/0 课 · 剩余 0 分钟 · 练习 0\/0/);
  assert.match(md, /## 数据来源/);
  assert.match(md, /hermes-usage:progress:v1/);
  assert.match(md, /hermes-usage:exercises:v1/);
  assert.ok(md.endsWith("\n"), "下载下来的 markdown 应以换行结尾");
  assert.equal(rowsOf(md).length, 0, "没有课程就不该有表格行");
});

test("生成时间用传入的 generatedAt，而不是当前时间", () => {
  const a = buildReport({ lessons: LESSONS, generatedAt: AT });
  const b = buildReport({ lessons: LESSONS, generatedAt: "2026-01-01T00:00:00.000Z" });
  assert.match(a, new RegExp(`生成时间：${AT.replace(/\./g, "\\.")}`));
  assert.match(b, /生成时间：2026-01-01T00:00:00\.000Z/);
  assert.notEqual(a, b, "generatedAt 不同，报告就该不同");
  assert.equal(buildReport({ lessons: LESSONS, generatedAt: AT }), a, "同一输入必须得到同一份报告（可复现）");
});

test("siteUrl 是可选的：给了才有那一行", () => {
  const withUrl = buildReport({ lessons: LESSONS, generatedAt: AT, siteUrl: SITE });
  assert.match(withUrl, new RegExp(`站点：${SITE.replace(/\//g, "\\/")}`));
  const withoutUrl = buildReport({ lessons: LESSONS, generatedAt: AT });
  assert.ok(!withoutUrl.includes("站点："));
  assert.ok(!withoutUrl.includes("undefined"));
});

test("按阶段分表格，表头与分隔行的列数都正确", () => {
  const md = buildReport({ lessons: LESSONS, generatedAt: AT, exercises: emptyExercises() });
  const lines = md.split("\n");

  // 两个阶段 → 两张表 → 两行分隔行，每行 5 个 `| --- |`
  const separators = lines.filter((l) => /^\|( --- \|)+$/.test(l));
  assert.equal(separators.length, 2, md);
  for (const sep of separators) {
    // 分隔行的「列数」按单元格数：相邻单元格共用一根竖线，数 ` --- ` 才是真列数
    assert.equal((sep.match(/ --- /g) || []).length, 5, `分隔行必须是 5 列：${sep}`);
    assert.deepEqual(columnsOf(sep), ["---", "---", "---", "---", "---"]);
  }
  const heads = lines.filter((l) => l.startsWith("| 课 |"));
  assert.equal(heads.length, 2);
  assert.equal(heads[0], "| 课 | 标题 | 耗时 | 完成 | 练习 |");
  assert.equal(columnsOf(heads[0]).length, 5);
  // 每行数据也必须是 5 格（标题里的竖线不能把一格切成两格）
  for (const row of rowsOf(md)) {
    assert.equal(columnsOf(row).length, 5, `列数不对：${row}`);
  }
  assert.match(md, /## 阶段 0 · 起步/);
  assert.match(md, /## 阶段 1 · 扩展能力/);
  assert.ok(md.indexOf("阶段 0") < md.indexOf("阶段 1"), "阶段的先后顺序要跟着课程列表");
});

test("完成列 ✅/○ 与练习列 n/m（部分完成）", () => {
  const md = buildReport({
    lessons: LESSONS,
    progress: doneState("L01"),
    exercises: exState({ L01: { "1": { at: AT } }, L15: { "1": { at: AT }, "2": { at: AT } } }),
    generatedAt: AT,
  });
  assert.equal(rowsOf(md).length, 3);
  assert.equal(rowsOf(md)[0], "| L00 | 装好 Hermes | 20 分钟 | ○ | 0/3 |");
  assert.equal(rowsOf(md)[1], "| L01 | 第一句话 | 25 分钟 | ✅ | 1/2 |");
  assert.equal(rowsOf(md)[2], "| L15 | 技能系统 | 45 分钟 | ○ | 2/5 |");
  assert.equal(marksOf(md, "✅"), 1);
  assert.equal(marksOf(md, "○"), 2);
});

test("全部完成：都是 ✅、都是 m/m、剩余 0 分钟", () => {
  const exercises = exState({
    L00: { "1": { at: AT }, "2": { at: AT }, "3": { at: AT } },
    L01: { "1": { at: AT }, "2": { at: AT } },
    L15: { "1": { at: AT }, "2": { at: AT }, "3": { at: AT }, "4": { at: AT }, "5": { at: AT } },
  });
  const md = buildReport({
    lessons: LESSONS,
    progress: doneState("L00", "L01", "L15"),
    exercises,
    generatedAt: AT,
  });
  assert.match(md, /完成 3\/3 课 · 剩余 0 分钟 · 练习 10\/10/);
  assert.equal(marksOf(md, "✅"), 3);
  assert.equal(marksOf(md, "○"), 0);
  assert.deepEqual(rowsOf(md).map((r) => columnsOf(r)[4]), ["3/3", "2/2", "5/5"]);
});

test("exercises 状态缺失时：练习列全写 —，且不报错", () => {
  const md = buildReport({ lessons: LESSONS, progress: doneState("L00"), generatedAt: AT });
  assert.equal(rowsOf(md).length, 3);
  for (const row of rowsOf(md)) {
    assert.ok(row.endsWith("| — |"), `没有练习数据就该写「—」：${row}`);
  }
  assert.ok(!md.includes("undefined"));
  assert.match(md, /练习 0\/10/, "分布已知：Z 是 0，W 仍是课程里的练习总数");
});

test("该课练习数为 0（或字段缺失）时那一行写 —，有练习的课照常 n/m", () => {
  const mixed = [
    { id: "L00", title: "装好", stage: 0, stage_name: "起步", minutes: 20, exercises: 3 },
    { id: "L02", title: "没有练习的课", stage: 0, stage_name: "起步", minutes: 10, exercises: 0 },
    { id: "L03", title: "字段都没写的课", stage: 0, stage_name: "起步", minutes: 10 },
  ];
  const md = buildReport({
    lessons: mixed,
    exercises: exState({ L00: { "1": { at: AT } }, L02: { "1": { at: AT } }, L03: { "1": { at: AT } } }),
    generatedAt: AT,
  });
  assert.deepEqual(rowsOf(md), [
    "| L00 | 装好 | 20 分钟 | ○ | 1/3 |",
    "| L02 | 没有练习的课 | 10 分钟 | ○ | — |",
    "| L03 | 字段都没写的课 | 10 分钟 | ○ | — |",
  ]);
});

test("幽灵课号被忽略：既不算完成，也不进练习计数", () => {
  const md = buildReport({
    lessons: LESSONS,
    progress: { version: 1, done: { L00: { at: AT }, L99: { at: AT } } },   // L99 早就不存在了
    exercises: exState({ L00: { "1": { at: AT } }, L99: { "1": { at: AT }, "2": { at: AT } } }),
    generatedAt: AT,
  });
  assert.ok(!md.includes("L99"), "课程列表里没有的课号不该出现在报告里");
  assert.equal(marksOf(md, "✅"), 1);
  assert.match(md, /完成 1\/3 课/);
  assert.match(md, /练习 1\/10/);
  assert.equal(rowsOf(md).length, 3);
});

test("题号超出该课练习数（正文改过）时不会算成 4/3", () => {
  const md = buildReport({
    lessons: LESSONS,
    exercises: exState({ L00: { "1": { at: AT }, "2": { at: AT }, "3": { at: AT }, "9": { at: AT } } }),
    generatedAt: AT,
  });
  assert.equal(rowsOf(md)[0], "| L00 | 装好 Hermes | 20 分钟 | ○ | 3/3 |");
  assert.equal(
    summarize({
      lessons: [{ id: "L02", title: "没有练习的课", stage: 0, minutes: 5, exercises: 0 }],
      exercises: exState({ L02: { "1": { at: AT } } }),
    }).exDone,
    0,
    "该课一道练习都没有（exercises: 0）时不计入",
  );
});

test("summarize 的五个数字都正确", () => {
  const exercises = exState({ L00: { "1": { at: AT } }, L01: { "2": { at: AT } } });
  assert.deepEqual(
    summarize({ lessons: LESSONS, progress: doneState("L01"), exercises }),
    { finished: 1, total: 3, minutesLeft: 65, exDone: 2, exTotal: 10 },
  );
  assert.deepEqual(summarize(), { finished: 0, total: 0, minutesLeft: 0, exDone: 0, exTotal: 0 });
  // 脏输入不能让它崩：lessons 不是数组、progress 缺 done、题号不是数字
  assert.deepEqual(summarize({ lessons: "nope", progress: null }).total, 0);
  assert.deepEqual(
    summarize({ lessons: LESSONS, exercises: exState({ L00: { abc: { at: AT } } }) }).exDone, 0,
    "题号不是数字的脏记录不算已做",
  );
});

test("标题里的竖线与换行不会破坏表格", () => {
  const md = buildReport({
    lessons: [{ id: "L07", title: "A | B\n换行了", stage: 2, stage_name: "工具", minutes: 30, exercises: 1 }],
    generatedAt: AT,
  });
  const row = rowsOf(md)[0];
  assert.equal(columnsOf(row).length, 5, `列数不对：${row}`);
  assert.equal(columnsOf(row)[1], "A \\| B 换行了");
  assert.ok(row.includes("A \\| B"), row);
  assert.ok(!row.includes("\n"));
});

test("练习打勾状态按 exercises.js 的真实结构读（集成一遍）", () => {
  let ex = toggleExercise(emptyExercises(), "L15", "1", AT);
  ex = toggleExercise(ex, "L15", "2", AT);
  const md = buildReport({ lessons: LESSONS, exercises: ex, generatedAt: AT });
  assert.equal(rowsOf(md)[2], "| L15 | 技能系统 | 45 分钟 | ○ | 2/5 |");
  assert.match(md, /练习 2\/10/);
});
