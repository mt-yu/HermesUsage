// web/assets/app.js —— 站点交互入口。
//
// 原则：静态 HTML 已经能完整阅读，本文件只做「增强」——
// 搜索、进度、目录高亮、复制代码、主题。任何一处失败都要安静降级，不能白屏。

import { escapeHtml, debounce, formatMinutes, lessonItems } from "./lib/util.js";
import { search, tokenizeToQuery } from "./lib/search.js";
import { toggleDone, completion, nextLesson, isDone, blocked } from "./lib/progress.js";
import {
  loadState, saveState, parseState, loadTheme, saveTheme, download,
  loadExercises, saveExercises,
} from "./lib/storage.js";
import { isExerciseDone, toggleExercise } from "./lib/exercises.js";
import { arrowTarget, cycleIndex } from "./lib/keynav.js";
import { pickActive, headingOffsets } from "./lib/toc.js";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const PREFIX = document.body.dataset.prefix || "";

/* 练习状态的合法性：课号来自 frontmatter（L15），题号来自渲染期的 data-ex。
   与 storage.js 的 parseExercises 用同一套正则 —— 两边必须一致，
   否则会出现「前端存进去了、下次加载被静默丢掉」的鬼打墙。 */
const LESSON_ID_RE = /^L\d{2,}$/;
const EX_ID_RE = /^\d+$/;

let lessons = [];
let state = loadState();
let exercises = loadExercises();
let searchIndex = null;

boot();

async function boot() {
  applyTheme(loadTheme());
  wireThemeToggle();
  wireNavDrawer();
  wirePalette();
  wireToc();
  wireCopyButtons();
  // 练习打勾与课间导航不依赖 data/index.json：放在 fetch 之前，
  // 索引拿不到时（file:// 打开、部署漏了 data/）这两件事照样能用。
  wireExercises();
  wireLessonArrows();

  try {
    const res = await fetch(`${PREFIX}data/index.json`);
    lessons = (await res.json()).lessons || [];
  } catch {
    return; // 拿不到索引就只保留静态阅读
  }
  wireProgressButtons();
  paint();
}

/* 「焦点在编辑控件里」的统一判定：单键快捷键（/ 、←/→）都要给输入让路。
   contenteditable 也算编辑区 —— 在可编辑正文里按 ← 同样是移光标。 */
function isTypingTarget() {
  const el = document.activeElement;
  if (!el) return false;
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName || "")) return true;
  return el.isContentEditable === true;
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

/* ------------------------------------------------------------ 练习打勾 */

/* 练习方框：渲染期输出的是静态 <span class="task-box" data-ex="1" aria-hidden="true">，
   这里把它升级成一个真正的 checkbox。

   课号取最近的 [data-lesson] 祖先 —— 课程页是 <article class="lesson" data-lesson="L15">。
   注意 <body data-lesson=""> 在首页 / 地图页是空串，教学页的 body 也带这个属性，
   所以「先校验格式再使用」不是洁癖：脏键喂进 exercises.js 后会被存储层静默丢弃，
   表现就是「点了有反应、刷新就没了」。格式不对就跳过，让它老实当个装饰方框。 */
function wireExercises() {
  for (const box of $$(".task-box")) {
    const host = box.closest("[data-lesson]");
    const lessonId = (host && host.dataset.lesson) || "";
    const exId = box.dataset.ex || "";
    if (!LESSON_ID_RE.test(lessonId) || !EX_ID_RE.test(exId)) continue;

    box.removeAttribute("aria-hidden");
    box.setAttribute("role", "checkbox");
    box.setAttribute("tabindex", "0");
    // 方框自己没有文字：拿整条练习的文字当可访问名，否则读屏只会念「复选框」
    const line = (box.closest("li") || box.parentElement).textContent.replace(/\s+/g, " ").trim();
    box.setAttribute("aria-label", line ? `练习：${line}` : `练习 ${exId}`);
    paintExercise(box, lessonId, exId);

    const flip = (e) => {
      e.preventDefault(); // 空格默认滚动页面
      exercises = toggleExercise(exercises, lessonId, exId);
      // 存不下（隐私模式）不拦着：本次会话里照样能看到勾
      saveExercises(exercises);
      paintExercise(box, lessonId, exId);
    };
    box.addEventListener("click", flip);
    box.addEventListener("keydown", (e) => {
      // Enter 与空格都切换 —— role=checkbox 的元素不会自己合成 click，
      // 所以这里不存在「键盘切一次、click 又切一次」的双触发
      if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") flip(e);
    });
  }
}

function paintExercise(box, lessonId, exId) {
  const done = isExerciseDone(exercises, lessonId, exId);
  // data-checked 是渲染期就写在标签上的属性（CSS 依赖它），aria-checked 是
  // 读屏读的：两个一起同步，不留一个真一个假
  box.dataset.checked = done ? "1" : "0";
  box.setAttribute("aria-checked", String(done));
}

/* ---------------------------------------------------------- 课间导航 */

/* ←/→ 翻到上一课 / 下一课。

   .prevnext 里第一课与最后一课的位置是空 <span>（CSS 用 :empty 隐藏），
   所以必须看「首/末子元素到底是不是 <a>」而不是「存不存在」：
   拿空 span 当链接会跳到 undefined。
   监听挂在 document 上、每次事件现算方向，不缓存启动时的判断 ——
   页面只有一处 .prevnext，但把「能不能翻」读成常量正是这类代码的老毛病。 */
function wireLessonArrows() {
  const nav = $(".prevnext");
  if (!nav) return;
  const first = nav.firstElementChild;
  const last = nav.lastElementChild;
  const prev = first && first.tagName === "A" ? first : null;
  const next = last && last.tagName === "A" ? last : null;
  if (!prev && !next) return;

  document.addEventListener("keydown", (e) => {
    // Ctrl/Cmd/Alt + ←→ 是系统的词间移动与前进后退，别抢
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    const palette = $("#palette");
    const target = arrowTarget(e.key, {
      typing: isTypingTarget(),
      inPalette: Boolean(palette && !palette.hidden),
      hasPrev: Boolean(prev),
      hasNext: Boolean(next),
    });
    if (!target) return;
    e.preventDefault(); // 否则 ←/→ 还会横向滚动页面
    location.href = (target === "prev" ? prev : next).getAttribute("href");
  });
}

/* ---------------------------------------------------------------- 搜索 */

function wirePalette() {
  const palette = $("#palette");
  const input = $("#palette-input");
  const list = $("#palette-results");
  const openBtn = $("#search-open");
  if (!palette || !input || !list) return;
  let cursor = 0;

  const close = () => {
    palette.hidden = true;
    input.value = "";
    list.innerHTML = "";
    // 焦点还给入口按钮：不然 Esc 之后焦点落在 <body> 上，键盘用户得从
    // 头 Tab 一遍整个顶栏才能回来
    if (openBtn) openBtn.focus();
  };
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
    if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) { open(); e.preventDefault(); return; }
    if (e.key === "/" && !isTypingTarget()) { open(); e.preventDefault(); return; }
    if (palette.hidden) return;
    /* 面板打开时 Tab 不切 DOM 焦点，而是移动高亮：面板里唯一能聚焦的只有
       输入框，真按 Tab 焦点会直接甩到面板外（对 aria-modal 的对话框来说
       就是「逃逸」）。出口是 Esc —— 它会把焦点还给 #search-open。 */
    if (e.key === "Tab") {
      e.preventDefault();
      const items = $$("li[data-url]", list);
      if (!items.length) return; // 没有结果就只兜住焦点，不动游标
      cursor = cycleIndex(cursor, e.shiftKey ? -1 : 1, items.length);
      render();
      return;
    }
    if (e.key === "Escape") close();
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
