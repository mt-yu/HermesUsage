// web/assets/lib/progress.js —— 学习进度的纯逻辑。
//
// 数据结构刻意与 progress/.state.json 完全一致（{"done": {"L00": {"at": "...", "note": ""}}}），
// 这样站点导出的 JSON 能直接给 python scripts/progress.py 用，不需要转换层。

export function emptyState() {
  return { version: 1, done: {} };
}

export function isDone(state, id) {
  return Boolean(state && state.done && state.done[id]);
}

export function toggleDone(state, id, at = new Date().toISOString()) {
  const done = { ...((state && state.done) || {}) };
  if (done[id]) delete done[id];
  else done[id] = { at, note: "" };
  return { version: 1, done };
}

export function completion(lessons, state) {
  const done = (state && state.done) || {};
  const finished = lessons.filter((l) => done[l.id]).length;
  const minutesLeft = lessons.filter((l) => !done[l.id]).reduce((n, l) => n + (l.minutes || 0), 0);
  return {
    finished,
    total: lessons.length,
    minutesLeft,
    percent: lessons.length ? Math.round((finished / lessons.length) * 100) : 0,
  };
}

export function blocked(lesson, state) {
  const done = (state && state.done) || {};
  return (lesson.prereq || []).filter((p) => !done[p]);
}

export function nextLesson(lessons, state) {
  const done = (state && state.done) || {};
  const open = lessons.filter((l) => !done[l.id]);
  return open.find((l) => (l.prereq || []).every((p) => done[p])) || open[0] || null;
}
