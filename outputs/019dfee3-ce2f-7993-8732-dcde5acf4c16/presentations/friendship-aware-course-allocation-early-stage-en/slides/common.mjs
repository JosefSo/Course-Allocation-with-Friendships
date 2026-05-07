export const TOTAL_SLIDES = 8;

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
};

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
    typeface: opts.face ?? C.body,
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
  text(slide, ctx, value.toUpperCase(), x + 16, y - 1, opts.w ?? 620, 24, {
    size: 9.5,
    color: dark ? "#C7D7EA" : C.muted,
    bold: true,
    valign: "middle",
    dark,
  });
}

export function title(slide, ctx, value, opts = {}) {
  const dark = Boolean(opts.dark);
  text(slide, ctx, value, opts.x ?? 58, opts.y ?? 94, opts.w ?? 1000, opts.h ?? 96, {
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

export function arrow(slide, ctx, x, y, w, color = C.teal) {
  line(slide, ctx, x, y + 9, w - 18, color, 2);
  text(slide, ctx, ">", x + w - 18, y, 16, 18, { size: 11, color, bold: true, align: "center" });
}

export function conceptBox(slide, ctx, label, body, x, y, w, h, color) {
  box(slide, ctx, x, y, w, h, { fill: C.panel, stroke: color });
  text(slide, ctx, label, x + 20, y + 18, w - 40, 20, { size: 10, color, bold: true });
  text(slide, ctx, body, x + 20, y + 48, w - 40, h - 58, {
    size: 17,
    color: C.ink,
    face: C.title,
    bold: true,
  });
}

export function metric(slide, ctx, value, label, note, x, y, color) {
  vline(slide, ctx, x, y, 62, color, 3);
  text(slide, ctx, value, x + 16, y - 4, 150, 34, {
    size: 27,
    color: C.ink,
    face: C.title,
    bold: true,
  });
  text(slide, ctx, label, x + 16, y + 34, 150, 16, { size: 9.5, color: C.muted, bold: true });
  text(slide, ctx, note, x + 16, y + 52, 170, 20, { size: 8.5, color: C.muted });
}

export function pill(slide, ctx, label, x, y, w, color) {
  box(slide, ctx, x, y, w, 34, { fill: C.panel, stroke: color });
  text(slide, ctx, label, x + 12, y + 9, w - 24, 14, { size: 10.5, color, bold: true, align: "center" });
}
