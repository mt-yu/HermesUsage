// web/assets/lib/toc.js —— 目录高亮（scrollspy）。

export function headingOffsets(root, selector = "h2[id], h3[id]") {
  return [...root.querySelectorAll(selector)].map((el) => ({
    id: el.id,
    top: el.getBoundingClientRect().top + window.scrollY,
  }));
}

export function pickActive(offsets, scrollY, margin = 90) {
  if (!offsets.length) return null;
  let active = offsets[0].id;
  for (const item of offsets) {
    if (item.top - margin <= scrollY) active = item.id;
    else break;
  }
  return active;
}
