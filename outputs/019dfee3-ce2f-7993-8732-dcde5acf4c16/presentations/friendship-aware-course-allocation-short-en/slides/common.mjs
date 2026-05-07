export const TOTAL_SLIDES = 9;

export const C = {
  bg: "#F7F3EA",
  panel: "#FFFCF4",
  ink: "#17212E",
  muted: "#56616F",
  faint: "#D7CDBE",
  faint2: "#E9DFCF",
  dark: "#17212E",
  dark2: "#223044",
  teal: "#0F766E",
  blue: "#355070",
  berry: "#9F1239",
  gold: "#B7791F",
  white: "#FFFFFF",
  title: "Aptos Display",
  body: "Aptos",
  mono: "Aptos Mono",
};

export const rows = [
  { mode: "swap-global", avgU: 352.612299, bestU: 354.755826, avgGTotal: 0.070808, minGTotal: 0.067269, avgGBase: 0.047782, minGBase: 0.042801 },
  { mode: "swap-personal", avgU: 340.181121, bestU: 343.801659, avgGTotal: 0.070852, minGTotal: 0.067094, avgGBase: 0.04068, minGBase: 0.03725 },
  { mode: "drop-add-global", avgU: 346.16876, bestU: 348.647529, avgGTotal: 0.070193, minGTotal: 0.063699, avgGBase: 0.042996, minGBase: 0.037615 },
  { mode: "drop-add-personal", avgU: 342.546983, bestU: 344.415963, avgGTotal: 0.070927, minGTotal: 0.066144, avgGBase: 0.046126, minGBase: 0.042581 },
  { mode: "hybrid-global", avgU: 365.025017, bestU: 366.177435, avgGTotal: 0.072126, minGTotal: 0.067076, avgGBase: 0.072559, minGBase: 0.066367 },
  { mode: "hybrid-personal", avgU: 337.391854, bestU: 340.457359, avgGTotal: 0.075803, minGTotal: 0.069521, avgGBase: 0.057403, minGBase: 0.049554 },
];

export function bg(slide, ctx, dark = false) {
  rect(slide, ctx, 0, 0, ctx.W, ctx.H, dark ? C.dark : C.bg);
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
    fontSize: opts.size ?? 16,
    color: opts.color ?? (dark ? C.white : C.ink),
    bold: Boolean(opts.bold),
    typeface: opts.face ?? (opts.mono ? C.mono : C.body),
    align: opts.align ?? "left",
    valign: opts.valign ?? "top",
    fill: opts.fill ?? "#00000000",
    line: opts.line ?? ctx.line(),
    insets: opts.insets ?? { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

export function line(slide, ctx, x, y, w, color = C.faint, weight = 1) {
  rect(slide, ctx, x, y, w, weight, color);
}

export function vline(slide, ctx, x, y, h, color = C.faint, weight = 1) {
  rect(slide, ctx, x, y, weight, h, color);
}

export function box(slide, ctx, x, y, w, h, opts = {}) {
  rect(slide, ctx, x, y, w, h, opts.fill ?? C.panel, {
    line: ctx.line(opts.stroke ?? C.faint, opts.weight ?? 1),
  });
}

export function kicker(slide, ctx, value, opts = {}) {
  const x = opts.x ?? 58;
  const y = opts.y ?? 50;
  const dark = Boolean(opts.dark);
  const color = opts.color ?? (dark ? "#F1D49D" : C.teal);
  rect(slide, ctx, x, y, 6, 22, color);
  text(slide, ctx, value.toUpperCase(), x + 16, y - 1, opts.w ?? 600, 24, {
    size: 9.5,
    color: dark ? "#C7D7EA" : C.muted,
    bold: true,
    valign: "middle",
    dark,
  });
}

export function title(slide, ctx, value, opts = {}) {
  const dark = Boolean(opts.dark);
  text(slide, ctx, value, opts.x ?? 58, opts.y ?? 94, opts.w ?? 1000, opts.h ?? 92, {
    size: opts.size ?? 36,
    color: opts.color ?? (dark ? C.white : C.ink),
    face: C.title,
    bold: true,
    dark,
  });
}

export function footer(slide, ctx, n, source, opts = {}) {
  const dark = Boolean(opts.dark);
  line(slide, ctx, 58, 668, 1164, dark ? "#41516A" : C.faint, 1);
  text(slide, ctx, source, 58, 682, 850, 18, {
    size: 8.5,
    color: dark ? "#9FB0C5" : "#7A6E60",
    dark,
  });
  text(slide, ctx, `${n}/${TOTAL_SLIDES}`, 1160, 682, 62, 18, {
    size: 9,
    color: dark ? "#C7D7EA" : C.muted,
    align: "right",
    dark,
  });
}

export function metric(slide, ctx, value, label, x, y, opts = {}) {
  const color = opts.color ?? C.teal;
  vline(slide, ctx, x, y, 54, color, 3);
  text(slide, ctx, value, x + 16, y - 4, opts.w ?? 150, 32, {
    size: opts.valueSize ?? 24,
    color: opts.valueColor ?? C.ink,
    face: C.title,
    bold: true,
  });
  text(slide, ctx, label, x + 16, y + 32, opts.w ?? 150, 18, {
    size: 9.5,
    color: C.muted,
    bold: true,
  });
}

export function arrow(slide, ctx, x, y, w, color = C.teal) {
  line(slide, ctx, x, y + 9, w - 18, color, 2);
  text(slide, ctx, ">", x + w - 18, y, 16, 18, { size: 11, color, bold: true, align: "center" });
}

export function callout(slide, ctx, label, body, x, y, w, h, color = C.teal) {
  box(slide, ctx, x, y, w, h, { fill: C.panel, stroke: color });
  text(slide, ctx, label, x + 18, y + 16, w - 36, 20, { size: 10, color, bold: true });
  text(slide, ctx, body, x + 18, y + 44, w - 36, h - 56, {
    size: 16,
    color: C.ink,
    face: C.title,
    bold: true,
  });
}

export function hBar(slide, ctx, label, value, x, y, opts = {}) {
  const min = opts.min ?? 0;
  const max = opts.max ?? 1;
  const labelW = opts.labelW ?? 190;
  const trackW = opts.trackW ?? 440;
  const color = opts.color ?? C.teal;
  const norm = (value - min) / Math.max(0.0001, max - min);
  text(slide, ctx, label, x, y - 3, labelW, 20, { size: opts.labelSize ?? 11.5, color: C.ink, bold: opts.bold });
  rect(slide, ctx, x + labelW, y + 4, trackW, 14, C.faint2);
  rect(slide, ctx, x + labelW, y + 4, Math.max(3, trackW * norm), 14, color);
  text(slide, ctx, opts.format ? opts.format(value) : value.toFixed(3), x + labelW + trackW + 16, y - 5, 82, 24, {
    size: opts.valueSize ?? 12,
    color,
    bold: true,
    align: "right",
  });
}

export function miniTable(slide, ctx, x, y, cols, dataRows, widths, opts = {}) {
  const rowH = opts.rowH ?? 38;
  let xx = x;
  cols.forEach((col, i) => {
    rect(slide, ctx, xx, y, widths[i], rowH, opts.headerFill ?? C.dark);
    text(slide, ctx, col, xx + 8, y + 11, widths[i] - 16, 16, { size: 9.5, color: C.white, bold: true, align: i ? "right" : "left" });
    xx += widths[i];
  });
  dataRows.forEach((row, r) => {
    xx = x;
    cols.forEach((_, i) => {
      rect(slide, ctx, xx, y + rowH * (r + 1), widths[i], rowH, r % 2 ? "#FFFFFF" : C.panel, {
        line: ctx.line(C.faint, 1),
      });
      text(slide, ctx, row[i], xx + 8, y + rowH * (r + 1) + 11, widths[i] - 16, 16, {
        size: 9.5,
        color: row.color ?? C.ink,
        bold: Boolean(row.bold),
        align: i ? "right" : "left",
      });
      xx += widths[i];
    });
  });
}
