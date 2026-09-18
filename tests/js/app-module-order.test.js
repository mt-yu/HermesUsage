// tests/js/app-module-order.test.js —— 顶层声明与 boot() 的顺序守卫。
//
// 起因（真实踩过）：给主题切换加三态时，`const THEME_CYCLE = [...]` 被写在了
// `boot();` 调用的**后面**。`boot()` 的第一句就是 `applyTheme(loadTheme())`，
// 而 applyTheme 要读 THEME_CYCLE —— const 在声明之前处于暂存死区（TDZ），
// 于是 boot() 在第一句就抛 ReferenceError。
//
// 这类 bug 的形态很坏：抛出发生在 async 函数里 → 变成「未处理的 Promise 拒绝」，
// 页面照常渲染、控制台不刷红（除非你专门监听 unhandledrejection），
// 但 boot() 里后面的接线（搜索、目录高亮、练习打勾、进度按钮）一条都没跑。
// 单测跑不出来，肉眼也看不出来 —— 是真实浏览器里点主题按钮毫无反应才暴露的。
//
// 守卫方式：源文件里所有顶层 const/let 的声明位置必须早于 `boot();` 这一行。
// 它不解析语法树，只看「声明语句的行号」，因此宁可保守（把 boot() 之前需要的一切
// 都放在前面），成本是零：真需要写在前面的东西本来就不多。

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const APP_JS = join(here, "..", "..", "web", "assets", "app.js");
const source = readFileSync(APP_JS, "utf8");
const lines = source.split("\n");

const bootLine = lines.findIndex((line) => /^boot\(\);/.test(line));

test("app.js 里有且只有一处顶层的 boot() 调用", () => {
  assert.notEqual(bootLine, -1, "找不到顶层 boot(); —— 本测试的前提变了，先看 app.js");
});

test("所有顶层 const/let 都声明在 boot() 调用之前（TDZ 守卫）", () => {
  const late = [];
  lines.forEach((line, i) => {
    if (i <= bootLine) return;
    if (/^(const|let|var)\s+[A-Za-z_$]/.test(line)) {
      late.push(`${i + 1}: ${line.trim()}`);
    }
  });
  assert.deepEqual(
    late,
    [],
    "这些顶层声明在 boot(); 之后 —— boot() 里如果读到它们会抛 TDZ ReferenceError，" +
      "而且会被吞成未处理的 Promise 拒绝（页面看似正常、接线全没跑）。把它们挪到 boot(); 之前。",
  );
});

test("主题常量在文件里可被 boot() 读到（三态切换的显式回归）", () => {
  const decl = lines.findIndex((line) => /^const THEME_CYCLE\s*=/.test(line));
  assert.notEqual(decl, -1, "找不到 const THEME_CYCLE —— 主题三态的实现变了？");
  assert.ok(decl < bootLine, `THEME_CYCLE 在第 ${decl + 1} 行、boot() 在第 ${bootLine + 1} 行`);
  for (const name of ["THEME_LABEL", "THEME_ICON"]) {
    const at = lines.findIndex((line) => new RegExp(`^const ${name}\\s*=`).test(line));
    assert.ok(at !== -1 && at < bootLine, `${name} 必须在 boot() 之前声明`);
  }
});
