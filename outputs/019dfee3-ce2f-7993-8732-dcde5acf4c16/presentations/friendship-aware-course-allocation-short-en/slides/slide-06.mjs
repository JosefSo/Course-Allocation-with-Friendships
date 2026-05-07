import { C, bg, box, footer, hBar, kicker, rect, rows, text, title } from "./common.mjs";

export async function slide06(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Result 1: utility");
  title(slide, ctx, "Hybrid-global is the clear winner on average utility.", {
    w: 900,
    h: 88,
    size: 35,
  });

  text(slide, ctx, "Average utility by mode, 30 runs each", 94, 206, 360, 20, {
    size: 12,
    color: C.muted,
    bold: true,
  });
  rows.forEach((r, i) => {
    hBar(slide, ctx, r.mode, r.avgU, 108, 252 + i * 52, {
      min: 335,
      max: 367,
      trackW: 360,
      color: r.mode === "hybrid-global" ? C.teal : r.mode.includes("personal") ? C.berry : C.blue,
      bold: r.mode === "hybrid-global",
      format: (v) => v.toFixed(3),
    });
  });

  box(slide, ctx, 788, 240, 318, 240, { fill: C.panel, stroke: C.faint });
  text(slide, ctx, "Best average utility", 818, 268, 180, 20, { size: 12, color: C.teal, bold: true });
  text(slide, ctx, "365.025017", 818, 318, 190, 42, { size: 34, color: C.teal, face: C.title, bold: true });
  text(slide, ctx, "hybrid-global", 820, 362, 150, 18, { size: 11, color: C.muted, bold: true });
  rect(slide, ctx, 820, 404, 236, 1, C.faint);
  text(slide, ctx, "Hybrid can use spare seats and swaps, so its local search neighborhood is richer than pure swap or pure drop-add.", 820, 430, 232, 40, {
    size: 11.5,
    color: C.ink,
  });

  footer(slide, ctx, 6, "Source: user screenshot table, Avg U column");
  return slide;
}
