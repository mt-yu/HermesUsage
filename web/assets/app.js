// web/assets/app.js —— 站点交互入口。
//
// 原则：静态 HTML 已经能完整阅读，本文件只做「增强」——
// 搜索、进度、目录高亮、复制代码、主题。任何一处失败都要安静降级，不能白屏。

import { escapeHtml, debounce, formatMinutes, lessonItems } from "./lib/util.js";
import { search, tokenizeToQuery } from "./lib/search.js";
import { toggleDone, completion, nextLesson, isDone, blocked } from "./lib/progress.js";
import { loadState, saveState, parseState, loadTheme, saveTheme, download } from "./lib/storage.js";
import { pickActive, headingOffsets } from "./lib/toc.js";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const PREFIX = document.body.dataset.prefix || "";

let lessons = [];
let state = loadState();
let searchIndex = null;

boot();

async function boot() {
  applyTheme(loadTheme());
  wireThemeToggle();
  wireNavDrawer();
  wirePalette();
  wireToc();
  wireCopyButtons();

  try {
    const res = await fetch(`${PREFIX}data/index.json`);
    lessons = (await res.json()).lessons || [];
  } catch {
    return; // 拿不到索引就只保留静态阅读
  }
  wireProgressButtons();
  paint();
}

/* ---------------------------------------------------------------- 进度 */

function paint() {
  const done = state.done || {};
  for (const li of lessonItems($$("li[data-lesson]"))) {
    li.classList.toggle("is-done", Boolean(done[li.dataset.lesson]));
  }
  const stats = completion(lessons, state);
  const count = $("#done-count");
  const bar = $("#bar-fill");
  const left = $("#min-left");
  const pill = $("#progress-pill");
  if (count) count.textContent = String(stats.finished);
  if (bar) bar.style.width = `${stats.percent}%`;
  if (left) left.textContent = formatMinutes(stats.minutesLeft);
  if (pill) pill.textContent = `${stats.finished}/${stats.total}`;

  const btn = $("#mark-done");
  if (btn) btn.textContent = isDone(state, btn.dataset.lesson) ? "取消完成标记" : "标记本课完成";
}

function commit(next) {
  state = next;
  if (!saveState(state)) {
    const out = $("#pc-out");
    if (out) {
      out.hidden = false;
      out.textContent = "这个浏览器不允许保存本地进度（隐私模式？），进度只在本次会话有效。";
    }
  }
  paint();
}

function wireProgressButtons() {
  const mark = $("#mark-done");
  if (mark) mark.addEventListener("click", () => commit(toggleDone(state, mark.dataset.lesson)));
  for (const li of lessonItems($$("li[data-lesson]"))) {
    const check = li.querySelector(".nav-check");
    if (!check) continue;
    // 侧栏/首页的圆圈可以直接点：把「打勾」这件最高频的事放到最顺手的地方
    check.style.cursor = "pointer";
    check.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      commit(toggleDone(state, li.dataset.lesson));
    });
  }

  const next = $("#next-lesson");
  if (next) {
    next.addEventListener("click", () => {
      const target = nextLesson(lessons, state);
      const out = $("#pc-out");
      if (!target) {
        if (out) { out.hidden = false; out.textContent = "全部课程都完成了。去 L90 毕业项目吧。"; }
        return;
      }
      const miss = blocked(target, state);
      if (out) {
        out.hidden = false;
        out.textContent = miss.length
          ? `${target.id} ${target.title} 的前置还没完成：${miss.join("、")}`
          : `下一课：${target.id} · ${target.title}（${target.minutes} 分钟）—— 正在打开…`;
      }
      if (!miss.length) location.href = `${PREFIX}${target.url}`;
    });
  }

  const exportBtn = $("#export-progress");
  if (exportBtn) {
    exportBtn.addEventListener("click", () => {
      download("progress.state.json", `${JSON.stringify(state, null, 2)}\n`);
    });
  }

  const importBtn = $("#import-progress");
  const fileInput = $("#import-file");
  if (importBtn && fileInput) {
    importBtn.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      const parsed = parseState(await file.text());
      const out = $("#pc-out");
      if (!parsed.ok) {
        if (out) { out.hidden = false; out.textContent = `导入失败：${parsed.error}`; }
        return;
      }
      commit(parsed.state);
      if (out) { out.hidden = false; out.textContent = `已导入 ${parsed.imported} 课的完成状态。`; }
    });
  }
}

/* ---------------------------------------------------------------- 搜索 */

function wirePalette() {
  const palette = $("#palette");
  const input = $("#palette-input");
  const list = $("#palette-results");
  const openBtn = $("#search-open");
  if (!palette || !input || !list) return;
  let cursor = 0;

  const close = () => { palette.hidden = true; input.value = ""; list.innerHTML = ""; };
  const open = async () => {
    palette.hidden = false;
    input.focus();
    if (!searchIndex) {
      try {
        const res = await fetch(`${PREFIX}data/search.json`);
        searchIndex = await res.json();
        // 检索用的「二字片段串」在客户端算一次（32 课，开销可忽略），
        // 复用 search.js 的分词函数，避免两处逻辑漂移
        for (const doc of searchIndex.docs) doc.tokens = tokenizeToQuery(doc.text);
      } catch {
        searchIndex = { docs: [] };
      }
    }
    render();
  };

  function render() {
    const hits = searchIndex ? search(searchIndex, input.value) : [];
    cursor = Math.min(cursor, Math.max(hits.length - 1, 0));
    list.innerHTML = hits.length
      ? hits.map((h, i) => `
        <li data-url="${escapeHtml(PREFIX + h.url)}" aria-selected="${i === cursor}">
          <div><b>${escapeHtml(h.id)} ${escapeHtml(h.title)}</b></div>
          <div class="pr-meta">${escapeHtml(h.snippet)}</div>
        </li>`).join("")
      : `<li class="pr-meta">${input.value ? "没有匹配的课程" : "输入关键词开始搜索（例如：cron、技能、回滚）"}</li>`;
  }

  input.addEventListener("input", debounce(render, 80));
  input.addEventListener("keydown", (e) => {
    const items = $$("li[data-url]", list);
    if (e.key === "ArrowDown") { cursor = Math.min(cursor + 1, items.length - 1); render(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { cursor = Math.max(cursor - 1, 0); render(); e.preventDefault(); }
    else if (e.key === "Enter" && items[cursor]) location.href = items[cursor].dataset.url;
    else if (e.key === "Escape") close();
  });
  list.addEventListener("click", (e) => {
    const li = e.target.closest("li[data-url]");
    if (li) location.href = li.dataset.url;
  });
  if (openBtn) openBtn.addEventListener("click", open);
  palette.addEventListener("click", (e) => { if (e.target === palette) close(); });
  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "");
    if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) { open(); e.preventDefault(); return; }
    if (e.key === "/" && !typing) { open(); e.preventDefault(); return; }
    if (e.key === "Escape" && !palette.hidden) close();
  });
}

/* ---------------------------------------------------------------- 目录 */

function wireToc() {
  const toc = $("#toc-side");
  if (!toc || !toc.querySelector("a")) return;
  const offsets = headingOffsets(document);
  if (!offsets.length) return;
  const links = new Map($$("a", toc).map((a) => [a.getAttribute("href").slice(1), a]));
  const onScroll = () => {
    const active = pickActive(offsets, window.scrollY);
    for (const [id, a] of links) a.classList.toggle("active", id === active);
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
}

/* ---------------------------------------------------------------- 代码复制 */

/* 复制到剪贴板：优先用异步 Clipboard API，但它只在安全上下文（https / localhost）
   存在 —— 通过局域网 IP 访问 Docker 部署的站点时它是 undefined，弹窗里点「复制」会全失败。
   所以失败时兜底到 textarea + execCommand。 */
async function copyText(text) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* 无焦点、权限被拒都会走到兜底路径 */
  }
  try {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  } catch {
    return false;
  }
}

function wireCopyButtons() {
  for (const pre of $$(".lesson pre")) {
    const code = pre.querySelector("code");
    if (!code) continue;
    const btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.type = "button";
    btn.textContent = "复制";
    btn.addEventListener("click", async () => {
      btn.textContent = (await copyText(code.innerText)) ? "已复制" : "复制失败";
      setTimeout(() => { btn.textContent = "复制"; }, 1200);
    });
    pre.append(btn);
  }
}

/* ---------------------------------------------------------------- 主题与抽屉 */

function applyTheme(theme) {
  const resolved = theme === "auto"
    ? (window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light")
    : theme;
  document.documentElement.dataset.theme = resolved === "dark" ? "dark" : "light";
}

function wireThemeToggle() {
  const btn = $("#theme-toggle");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    saveTheme(next);
    applyTheme(next);
  });
}

function wireNavDrawer() {
  const toggle = $("#nav-toggle");
  const sidebar = $("#sidebar");
  if (!toggle || !sidebar) return;
  toggle.addEventListener("click", () => {
    const open = sidebar.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (e) => {
    if (!sidebar.classList.contains("is-open")) return;
    if (sidebar.contains(e.target) || toggle.contains(e.target)) return;
    sidebar.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
  });
}
