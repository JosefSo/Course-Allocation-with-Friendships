import { C, bg, box, footer, hBar, kicker, rows, text, title } from "./common.mjs";

export async function slide07(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Result 2: fairness");
  title(slide, ctx, "Fairness gives a different winner: drop-add-global has the lowest average total Gini.", {
    w: 1000,
    h: 92,
    size: 32,
  });

  text(slide, ctx, "Average G_total by mode (lower is better)", 84, 214, 360, 20, {
    size: 12,
    color: C.muted,
    bold: true,
  });
  rows.forEach((r, i) => {
    hBar(slide, ctx, r.mode, r.avgGTotal, 92, 258 + i * 45, {
      min: 0.0695,
      max: 0.076,
      labelW: 188,
      trackW: 306,
      color: r.mode === "drop-add-global" ? C.teal : C.berry,
      bold: r.mode === "drop-add-global",
      format: (v) => v.toFixed(6),
      valueSize: 10.5,
    });
  });

  box(slide, ctx, 722, 224, 392, 302, { fill: C.panel, stroke: C.faint });
  text(slide, ctx, "Fairness interpretation", 752, 250, 210, 20, { size: 12, color: C.berry, bold: true });
  text(slide, ctx, "0.070193", 754, 300, 160, 42, { size: 34, color: C.teal, face: C.title, bold: true });
  text(slide, ctx, "lowest Avg G_total, drop-add-global", 756, 344, 230, 18, { size: 10.5, color: C.muted, bold: true });
  text(slide, ctx, "0.075803", 754, 398, 160, 42, { size: 30, color: C.berry, face: C.title, bold: true });
  text(slide, ctx, "highest Avg G_total, hybrid-personal", 756, 438, 230, 18, { size: 10.5, color: C.muted, bold: true });
  text(slide, ctx, "The best utility method is not the most equal method. The evaluation therefore needs both welfare and inequality metrics.", 754, 482, 294, 28, {
    size: 11.5,
    color: C.ink,
  });

  footer(slide, ctx, 7, "Source: user screenshot table, Avg G_total column");
  return slide;
}
