// web/assets/lib/report.js —— 「导出学习报告」的纯逻辑：把浏览器里的学习痕迹
// 变成一份可交付的 markdown。
//
// 为什么做成纯函数
// ----------------
// 这份报告是**给人看、也会被存下来**的东西：读者可能把它贴进 issue、放进周报、
// 交给同事，而它一旦算错，错的是一句「你已完成 3/32 课」这样与事实相反的陈述 ——
// 浏览器里点一下就下载了，没有任何东西拦得住。所以：
//   * 不碰 localStorage（progress / exercises 由调用方传进来）；
//   * 不调 `new Date()`（generatedAt 由调用方给，报告因此可断言、可复现）；
//   * 不碰 DOM（写文件由 app.js 用 storage.js 的 download 完成）。
// 于是 `node --test` 就能把报告的确切文本钉死，而 app.js 只剩「取值 + 下载」两行。
//
// 数字只有一份来源：完成数/剩余分钟来自 progress.js 的 completion()，
// 练习总数来自构建期写进 `data/index.json` 的 exercises（见 scripts/site_render.py
// 的 count_exercises），已做数来自浏览器的练习题状态（lib/exercises.js）。这里
// 不重新发明任何一条规则，只把它们排成一张表。

import { completion } from "./progress.js";

const REPORT_TITLE = "# Hermes Agent 教程 · 学习报告";

// 数据来源一节要写清「数据在哪、怎么拿全」：读者拿到一份 markdown 之后，
// 最常问的两件事就是「这数从哪来的」和「我想要更细的怎么办」。
const SOURCE_NOTES = [
  "## 数据来源",
  "",
  "- 这份报告在**你自己的浏览器**里生成：数据全部来自本机 localStorage，没有任何上传。",
  "- 课程完成状态读自键 `hermes-usage:progress:v1`（结构 `{ version, done }`）。",
  "- 练习打勾状态读自键 `hermes-usage:exercises:v1`（结构 `{ version, lessons }`）。",
  "- 「练习」列的 `n/m`：`n` = 你打勾的题数，`m` = 该课正文里的练习题总数（构建期由 `scripts/site_render.py` 的 `count_exercises` 数出来，写在 `data/index.json` 的 `exercises` 字段里）。",
  "- 「完成」列的 ✅ / ○ 只表示有没有标记完成，不含完成时间与备注。",
  "- 完整数据（每课的完成时间、备注、逐题打勾时间）可用首页的「导出进度 JSON」得到，文件名 `progress.state.json`；它与 `python scripts/progress.py` 的本地状态同构。",
];

/** 课程列表：只认「有 id 的对象」，并把 minutes / exercises 归一化成非负整数。 */
function normalizeLessons(lessons) {
  if (!Array.isArray(lessons)) return [];
  return lessons
    .filter((l) => l && typeof l === "object" && typeof l.id === "string" && l.id)
    .map((l) => ({ ...l, minutes: toPositiveInt(l.minutes), exercises: toPositiveInt(l.exercises) }));
}

function toPositiveInt(value) {
  const n = Number(value);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 0;
}

/**
 * 该课已打勾的题数。
 *
 * 只数数字题号：与 storage.js 的 parseExercises 同一套合法性规则（题号来自渲染期的
 * data-ex，永远是纯数字）。脏键在这里被忽略，而不是让它混进「3/5」里。
 * 课程列表里没有的课号（幽灵课：正文改过、课被删过）由调用方按课程遍历天然排除。
 */
function doneExercises(exercises, lessonId) {
  const all = exercises && typeof exercises === "object" ? exercises.lessons : null;
  const box = all && typeof all === "object" ? all[lessonId] : null;
  if (!box || typeof box !== "object") return 0;
  return Object.keys(box).filter((k) => /^\d+$/.test(k)).length;
}

/** 该课做完的题数：**封顶**在练习总数上。正文改过之后旧状态里可能留着超出的题号，
 *  不封顶就会写出「4/3」这种不可能的数字。 */
function cappedDone(exercises, lesson) {
  return Math.min(doneExercises(exercises, lesson.id), lesson.exercises);
}

/**
 * 报告的五个数字。`finished / total / minutesLeft` 直接来自 progress.js 的
 * completion() —— 首页进度卡用的是同一个函数，两处不可能给出不同的「剩余 725 分钟」。
 */
export function summarize({ lessons, progress, exercises } = {}) {
  const list = normalizeLessons(lessons);
  const stats = completion(list, progress);
  let exDone = 0;
  let exTotal = 0;
  for (const lesson of list) {
    exTotal += lesson.exercises;
    exDone += cappedDone(exercises, lesson);
  }
  return {
    finished: stats.finished,
    total: stats.total,
    minutesLeft: stats.minutesLeft,
    exDone,
    exTotal,
  };
}

/**
 * 生成学习报告的 markdown。所有输入都可缺省：缺什么就少写什么，绝不抛异常 ——
 * 一个按下就报错的「导出」按钮，比没有这个按钮更让人不信任。
 *
 * @param {object}   [opts]
 * @param {Array}    [opts.lessons]     `data/index.json` 的 lessons（含 exercises 总数）
 * @param {object}   [opts.progress]    `{ version, done: { L15: { at, note } } }`
 * @param {object}   [opts.exercises]   `{ version, lessons: { L15: { "1": { at } } } }`
 * @param {string}   [opts.generatedAt] ISO 时间串，由调用方给（本函数不读时钟）
 * @param {string}   [opts.siteUrl]     站点地址，给了才多一行
 * @returns {string} markdown 文本（以换行结尾）
 */
export function buildReport({ lessons, progress, exercises, generatedAt, siteUrl } = {}) {
  const list = normalizeLessons(lessons);
  const stats = summarize({ lessons: list, progress, exercises });
  const done = (progress && typeof progress === "object" && progress.done) || {};
  // 练习状态整体缺席（undefined）时，练习列一律写「—」：这时我们只知道「这课有几道题」，
  // 完全不知道读者做了几道，写「0/5」会是一句没有依据的话。
  const hasExerciseState = Boolean(exercises) && typeof exercises === "object";

  const lines = [REPORT_TITLE, "", `生成时间：${generatedAt || "（未提供）"}`];
  if (siteUrl) lines.push(`站点：${siteUrl}`);
  lines.push(
    "",
    `完成 ${stats.finished}/${stats.total} 课 · 剩余 ${stats.minutesLeft} 分钟 · 练习 ${stats.exDone}/${stats.exTotal}`,
    "",
  );

  const groups = groupByStage(list);
  if (!groups.length) {
    lines.push("课程列表为空：这份报告里还没有可统计的课程。", "");
  }
  for (const group of groups) {
    lines.push(`## ${group.title}`, "");
    lines.push("| 课 | 标题 | 耗时 | 完成 | 练习 |", "| --- | --- | --- | --- | --- |");
    for (const lesson of group.lessons) {
      const ex = !hasExerciseState || lesson.exercises === 0
        ? "—"
        : `${cappedDone(exercises, lesson)}/${lesson.exercises}`;
      lines.push(
        `| ${lesson.id} | ${cell(lesson.title)} | ${lesson.minutes} 分钟 | `
        + `${done[lesson.id] ? "✅" : "○"} | ${ex} |`,
      );
    }
    lines.push("");
  }

  lines.push(...SOURCE_NOTES);
  return lines.join("\n") + "\n";
}

/**
 * 按阶段分组出表格。**保持 lessons 的给定顺序**，不在报告里再排一次：
 * `data/index.json` 的课程顺序就是站点侧栏、首页、地图页的顺序，报告跟着它走，
 * 才不会出现「报告里阶段 1 排在阶段 0 前面」这种只在报告里成立的新规则。
 */
function groupByStage(list) {
  const groups = new Map();
  for (const lesson of list) {
    const key = lesson.stage == null ? "__none__" : String(lesson.stage);
    let group = groups.get(key);
    if (!group) {
      group = { title: stageTitle(lesson), lessons: [] };
      groups.set(key, group);
    }
    group.lessons.push(lesson);
  }
  return [...groups.values()];
}

function stageTitle(lesson) {
  if (lesson.stage == null) return "未分阶段";
  const name = typeof lesson.stage_name === "string" ? lesson.stage_name.trim() : "";
  return name ? `阶段 ${lesson.stage} · ${name}` : `阶段 ${lesson.stage}`;
}

/** markdown 表格单元格：竖线会把一格切成两格（列数对不上），换行会把表格截断。 */
function cell(value) {
  const text = String(value == null ? "" : value).replace(/\|/g, "\\|").replace(/\s+/g, " ").trim();
  return text || "（无标题）";
}
