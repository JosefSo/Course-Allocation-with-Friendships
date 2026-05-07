export const TOTAL_SLIDES = 14;

export const S = {
  bg: "#F7F3EA",
  bg2: "#EFE7D9",
  ink: "#17212E",
  muted: "#56616F",
  faint: "#D7CDBE",
  faint2: "#E9DFCF",
  dark: "#17212E",
  dark2: "#223044",
  teal: "#0F766E",
  teal2: "#BFE3DC",
  berry: "#9F1239",
  berry2: "#E9B8C6",
  gold: "#B7791F",
  gold2: "#F1D49D",
  blue: "#355070",
  white: "#FFFFFF",
  titleFont: "Aptos Display",
  bodyFont: "Aptos",
  monoFont: "Aptos Mono",
};

export const DATA = {
  postIters: [0, 1, 5, 10, 20],
  utility: {
    "hybrid-global": [371.310059, 382.631291, 384.804574, 384.815154, 384.815154],
    "swap-global": [371.310059, 372.018039, 374.308638, 376.473502, 379.51645],
    "drop-add-global": [371.310059, 372.164515, 372.129036, 372.295586, 372.274612],
    "hybrid-personal": [371.310059, 369.007255, 369.462452, 369.421339, 369.861994],
  },
  summary: {
    baselineU: 371.310,
    hybridU5: 384.805,
    hybridPct: 3.63,
    swapPct: 2.21,
    dropAddPct: 0.26,
    hybridPersonalPct: -0.39,
    friendBase: 3.715,
    friendHybrid: 4.697,
    friendPct: 26.44,
    avgPosBase: 2.186,
    avgPosHybrid: 2.434,
    top3Base: 0.872,
    top3Hybrid: 0.796,
    giniBase: 0.05238,
    giniHybrid: 0.05576,
  },
};

export function bg(slide, ctx, dark = false) {
  rect(slide, ctx, 0, 0, ctx.W, ctx.H, dark ? S.dark : S.bg);
}

export function rect(slide, ctx, x, y, w, h, fill, opts = {}) {
  return ctx.addShape(slide, {
    left: x,
    top: y,
    width: w,
    height: h,
    geometry: opts.geometry ?? "rect",
    fill,
    line: opts.line ?? ctx.line(),
    name: opts.name,
  });
}

export function text(slide, ctx, value, x, y, w, h, opts = {}) {
  const dark = Boolean(opts.dark);
  return ctx.addText(slide, {
    text: String(value ?? ""),
    left: x,
    top: y,
    width: w,
    height: h,
    fontSize: opts.size ?? 18,
    color: opts.color ?? (dark ? "#FFFFFF" : S.ink),
    bold: Boolean(opts.bold),
    typeface: opts.face ?? (opts.mono ? S.monoFont : S.bodyFont),
    align: opts.align ?? "left",
    valign: opts.valign ?? "top",
    fill: opts.fill ?? "#00000000",
    line: opts.line ?? ctx.line(),
    insets: opts.insets ?? { left: 0, right: 0, top: 0, bottom: 0 },
    name: opts.name,
  });
}

export function rule(slide, ctx, x, y, w, color = S.faint, weight = 1) {
  rect(slide, ctx, x, y, w, weight, color);
}

export function vrule(slide, ctx, x, y, h, color = S.faint, weight = 1) {
  rect(slide, ctx, x, y, weight, h, color);
}

export function kicker(slide, ctx, label, opts = {}) {
  const x = opts.x ?? 58;
  const y = opts.y ?? 48;
  const dark = Boolean(opts.dark);
  const color = opts.color ?? (dark ? S.gold2 : S.teal);
  rect(slide, ctx, x, y + 1, 6, 22, color);
  text(slide, ctx, label.toUpperCase(), x + 16, y, opts.w ?? 520, 24, {
    size: 10,
    color: dark ? "#D9E2EF" : S.muted,
    bold: true,
    valign: "middle",
    insets: { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

export function title(slide, ctx, value, opts = {}) {
  const dark = Boolean(opts.dark);
  text(slide, ctx, value, opts.x ?? 58, opts.y ?? 86, opts.w ?? 930, opts.h ?? 94, {
    size: opts.size ?? 36,
    color: opts.color ?? (dark ? S.white : S.ink),
    face: S.titleFont,
    bold: true,
    dark,
  });
}

export function subtitle(slide, ctx, value, x, y, w, h, opts = {}) {
  text(slide, ctx, value, x, y, w, h, {
    size: opts.size ?? 15,
    color: opts.color ?? (opts.dark ? "#C7D7EA" : S.muted),
    dark: opts.dark,
  });
}

export function footer(slide, ctx, n, source, opts = {}) {
  const dark = Boolean(opts.dark);
  rule(slide, ctx, 58, 668, 1164, dark ? "#41516A" : S.faint, 1);
  text(slide, ctx, source, 58, 682, 900, 18, {
    size: 8.5,
    color: dark ? "#9FB0C5" : "#7A6E60",
    dark,
  });
  text(slide, ctx, `${n}/${TOTAL_SLIDES}`, 1162, 682, 60, 18, {
    size: 9,
    color: dark ? "#C7D7EA" : S.muted,
    align: "right",
    dark,
  });
}

export function box(slide, ctx, x, y, w, h, opts = {}) {
  rect(slide, ctx, x, y, w, h, opts.fill ?? "#00000000", {
    line: ctx.line(opts.stroke ?? S.faint, opts.weight ?? 1),
  });
}

export function labelBox(slide, ctx, label, body, x, y, w, h, opts = {}) {
  box(slide, ctx, x, y, w, h, {
    fill: opts.fill ?? "#00000000",
    stroke: opts.stroke ?? S.faint,
  });
  text(slide, ctx, label, x + 18, y + 16, w - 36, 20, {
    size: opts.labelSize ?? 10,
    color: opts.labelColor ?? S.teal,
    bold: true,
  });
  text(slide, ctx, body, x + 18, y + 42, w - 36, h - 54, {
    size: opts.bodySize ?? 16,
    color: opts.bodyColor ?? S.ink,
    face: opts.face ?? S.titleFont,
    bold: opts.bold ?? true,
  });
}

export function metric(slide, ctx, value, label, note, x, y, opts = {}) {
  const dark = Boolean(opts.dark);
  const color = opts.color ?? (dark ? S.gold2 : S.teal);
  vrule(slide, ctx, x, y - 2, 60, color, 3);
  text(slide, ctx, value, x + 16, y, opts.w ?? 165, 34, {
    size: opts.valueSize ?? 28,
    color: opts.valueColor ?? (dark ? S.white : S.ink),
    face: S.titleFont,
    bold: true,
    dark,
  });
  text(slide, ctx, label, x + 16, y + 36, opts.w ?? 165, 18, {
    size: opts.labelSize ?? 9.5,
    color: opts.labelTextColor ?? (dark ? "#C7D7EA" : S.muted),
    bold: true,
    dark,
  });
  text(slide, ctx, note, x + 16, y + 54, opts.w ?? 165, 24, {
    size: opts.noteSize ?? 8.5,
    color: opts.noteColor ?? (dark ? "#9FB0C5" : S.muted),
    dark,
  });
}

export function hBar(slide, ctx, item, x, y, w, opts = {}) {
  const max = opts.max ?? 1;
  const barW = Math.max(0, w * (item.value / max));
  text(slide, ctx, item.label, x, y - 2, opts.labelW ?? 180, 22, {
    size: opts.labelSize ?? 12,
    color: opts.labelColor ?? S.ink,
    bold: Boolean(item.bold),
  });
  rect(slide, ctx, x + (opts.labelW ?? 180), y + 3, w, 14, opts.track ?? S.faint2);
  rect(slide, ctx, x + (opts.labelW ?? 180), y + 3, barW, 14, item.color ?? S.teal);
  text(slide, ctx, item.note ?? item.value, x + (opts.labelW ?? 180) + w + 14, y - 3, opts.noteW ?? 90, 22, {
    size: opts.valueSize ?? 11,
    color: opts.valueColor ?? S.ink,
    bold: true,
    align: "right",
  });
}

export function vBars(slide, ctx, x, y, w, h, items, opts = {}) {
  const max = opts.max ?? Math.max(...items.map((d) => d.value), 1);
  const min = opts.min ?? 0;
  const gap = opts.gap ?? 22;
  const barW = (w - gap * (items.length - 1)) / items.length;
  items.forEach((item, i) => {
    const norm = (item.value - min) / Math.max(0.0001, max - min);
    const bh = Math.max(2, h * norm);
    const bx = x + i * (barW + gap);
    rect(slide, ctx, bx, y + h - bh, barW, bh, item.color ?? S.teal);
    text(slide, ctx, item.valueLabel ?? String(item.value), bx - 10, y + h - bh - 24, barW + 20, 20, {
      size: opts.valueSize ?? 10,
      color: opts.valueColor ?? S.ink,
      bold: true,
      align: "center",
    });
    text(slide, ctx, item.label, bx - 18, y + h + 14, barW + 36, 34, {
      size: opts.labelSize ?? 9.5,
      color: opts.labelColor ?? S.muted,
      align: "center",
    });
  });
  rule(slide, ctx, x - 6, y + h, w + 12, opts.axisColor ?? S.faint, 1);
}

export function stepNode(slide, ctx, n, label, body, x, y, w, h, opts = {}) {
  box(slide, ctx, x, y, w, h, {
    fill: opts.fill ?? "#00000000",
    stroke: opts.stroke ?? S.faint,
  });
  text(slide, ctx, String(n).padStart(2, "0"), x + 16, y + 16, 40, 26, {
    size: 18,
    color: opts.numColor ?? S.teal,
    face: S.titleFont,
    bold: true,
  });
  text(slide, ctx, label, x + 64, y + 17, w - 82, 24, {
    size: opts.labelSize ?? 15,
    color: opts.color ?? S.ink,
    bold: true,
  });
  text(slide, ctx, body, x + 64, y + 48, w - 82, h - 58, {
    size: opts.bodySize ?? 10.5,
    color: opts.bodyColor ?? S.muted,
  });
}

export function arrowText(slide, ctx, x, y, w, color = S.teal) {
  rule(slide, ctx, x, y + 8, w - 16, color, 2);
  text(slide, ctx, "→", x + w - 18, y - 6, 24, 24, {
    size: 18,
    color,
    bold: true,
    align: "center",
  });
}

export function formula(slide, ctx, value, x, y, w, h, opts = {}) {
  box(slide, ctx, x, y, w, h, {
    fill: opts.fill ?? "#FFFCF4",
    stroke: opts.stroke ?? S.faint,
  });
  text(slide, ctx, value, x + 20, y + 18, w - 40, h - 34, {
    size: opts.size ?? 22,
    color: opts.color ?? S.ink,
    face: opts.face ?? S.titleFont,
    bold: opts.bold ?? true,
    valign: "middle",
  });
}

export function percent(value, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}
