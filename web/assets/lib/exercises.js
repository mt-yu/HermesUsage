// web/assets/lib/exercises.js —— 练习题打勾状态的纯逻辑。
//
// 为什么单独一个文件、单独一个存储键
// ----------------------------------
// 「这课读完了」（progress.js）和「这课的 5 道练习做完了几道」是两件事：
// 前者是线性进度，后者是逐题粒度。硬塞进 progress 的 done 里会让导出文件
// 与 progress/.state.json 的既有格式冲突（那份文件是 python scripts/progress.py
// 在读的），所以练习状态走自己的键与自己的结构。
//
// 主键是「课号 + 题号」：课号来自课程 frontmatter（L15），题号来自渲染期
// 写入的 data-ex（见 scripts/site_render.py 的 preprocess_tasklist）。
// 题号在一课内从 1 递增，所以它稳定 —— 只要不删改正文里的练习顺序。
//
// 结构刻意与 progress.js 同风格：
//   { version: 1, lessons: { "L15": { "1": { at: "2026-09-16T07:00:00Z" }, "3": { at: "…" } } } }
// 已做 = 键存在；没做 = 键不存在。**不写 false**：多一种「存在但为假」的
// 表示，将来读数据时每个地方都要多判断一次，纯属给自己埋坑。

export const emptyExercises = () => ({ version: 1, lessons: {} });

export function isExerciseDone(state, lessonId, exId) {
  return Boolean(state && state.lessons && state.lessons[lessonId] && state.lessons[lessonId][exId]);
}

/**
 * 打勾 / 取消。不可变：返回新对象，原对象一动不动。
 *
 * 取消时删掉题号键；如果这一课因此没有任何已做题，连课号键一起删掉 ——
 * 否则导出文件里会慢慢积累一堆 `"L07": {}` 的空壳，导入时看着像数据损坏。
 */
export function toggleExercise(state, lessonId, exId, at = new Date().toISOString()) {
  const lessons = { ...((state && state.lessons) || {}) };
  const current = { ...(lessons[lessonId] || {}) };
  if (current[exId]) {
    delete current[exId];
    if (Object.keys(current).length === 0) delete lessons[lessonId];
    else lessons[lessonId] = current;
  } else {
    current[exId] = { at };
    lessons[lessonId] = current;
  }
  return { version: 1, lessons };
}

export function countDone(state, lessonId) {
  const lesson = (state && state.lessons && state.lessons[lessonId]) || {};
  return Object.keys(lesson).length;
}
