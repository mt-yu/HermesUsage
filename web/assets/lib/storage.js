// web/assets/lib/storage.js —— localStorage 读写 + 导入校验 + 文件下载。
//
// 失败一律降级为「空状态 / false」，绝不抛异常：站点在 file:// 下打开、
// 或用户在隐私模式里用，都应该照常能读书，只是进度存不下来。

import { emptyState } from "./progress.js";
import { emptyExercises } from "./exercises.js";

export const STORAGE_KEY = "hermes-usage:progress:v1";
export const EXERCISE_KEY = "hermes-usage:exercises:v1";
export const THEME_KEY = "hermes-usage:theme:v1";

export function loadState(storage = globalThis.localStorage) {
  try {
    const raw = storage && storage.getItem(STORAGE_KEY);
    if (!raw) return emptyState();
    const parsed = parseState(raw);
    return parsed.ok ? parsed.state : emptyState();
  } catch {
    return emptyState();
  }
}

export function saveState(state, storage = globalThis.localStorage) {
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

export function parseState(text) {
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    return { ok: false, error: "不是合法的 JSON" };
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return { ok: false, error: "顶层必须是对象" };
  }
  if (data.done != null && (typeof data.done !== "object" || Array.isArray(data.done))) {
    return { ok: false, error: "done 必须是对象" };
  }
  const clean = emptyState();
  for (const [id, value] of Object.entries(data.done || {})) {
    if (!/^L\d{2,}$/.test(id)) continue;
    clean.done[id] = {
      at: typeof value?.at === "string" ? value.at : "",
      note: typeof value?.note === "string" ? value.note : "",
    };
  }
  return { ok: true, state: clean, imported: Object.keys(clean.done).length };
}

// —— 练习题打勾状态：独立键的原因见 web/assets/lib/exercises.js 的注释 ——

export function loadExercises(storage = globalThis.localStorage) {
  try {
    const raw = storage && storage.getItem(EXERCISE_KEY);
    if (!raw) return emptyExercises();
    const parsed = parseExercises(raw);
    return parsed.ok ? parsed.state : emptyExercises();
  } catch {
    return emptyExercises();
  }
}

export function saveExercises(state, storage = globalThis.localStorage) {
  try {
    storage.setItem(EXERCISE_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

/**
 * 校验练习状态（导入文件时用）。与 parseState 同一套路：坏 JSON、非对象顶层、
 * 类型不对的 lessons 直接判失败；单条脏数据（课号不是 L15、题号不是整数、
 * 值是字符串）静默丢弃，不因为一道坏题毁掉读者整个学期的记录。
 */
export function parseExercises(text) {
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    return { ok: false, error: "不是合法的 JSON" };
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return { ok: false, error: "顶层必须是对象" };
  }
  if (data.lessons != null && (typeof data.lessons !== "object" || Array.isArray(data.lessons))) {
    return { ok: false, error: "lessons 必须是对象" };
  }
  const clean = emptyExercises();
  let imported = 0;
  for (const [lessonId, exercises] of Object.entries(data.lessons || {})) {
    if (!/^L\d{2,}$/.test(lessonId)) continue;
    if (!exercises || typeof exercises !== "object" || Array.isArray(exercises)) continue;
    for (const [exId, value] of Object.entries(exercises)) {
      if (!/^\d+$/.test(exId)) continue;
      if (!clean.lessons[lessonId]) clean.lessons[lessonId] = {};
      clean.lessons[lessonId][exId] = { at: typeof value?.at === "string" ? value.at : "" };
      imported += 1;
    }
  }
  return { ok: true, state: clean, imported };
}

export function loadTheme(storage = globalThis.localStorage, fallback = "auto") {
  try {
    return storage.getItem(THEME_KEY) || fallback;
  } catch {
    return fallback;
  }
}

export function saveTheme(theme, storage = globalThis.localStorage) {
  try {
    storage.setItem(THEME_KEY, theme);
  } catch {
    /* 存不下就算了：主题不是关键数据 */
  }
}

export function download(filename, text) {
  const blob = new Blob([text], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
