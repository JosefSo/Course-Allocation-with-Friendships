import { C, bg, box, footer, kicker, metric, rect, text, title } from "./common.mjs";

export async function slide07(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Preliminary progress");
  title(slide, ctx, "I have started using experiments to check that the pipeline works.", {
    w: 980,
    h: 88,
    size: 35,
  });

  box(slide, ctx, 88, 224, 1098, 118, { fill: C.panel, stroke: C.faint });
  metric(slide, ctx, "180", "completed runs", "prototype batch", 136, 252, C.blue);
  metric(slide, ctx, "6", "modes tested", "for comparison only", 396, 252, C.teal);
  metric(slide, ctx, "20-49", "seed range", "reproducibility check", 656, 252, C.gold);
  metric(slide, ctx, "Gini", "fairness metric", "tracked, not finalized", 916, 252, C.berry);

  box(slide, ctx, 144, 426, 438, 110, { fill: C.panel, stroke: C.teal });
  text(slide, ctx, "What I can already show", 174, 452, 210, 20, { size: 12, color: C.teal, bold: true });
  text(slide, ctx, "The model can run, produce allocations, and output utility and fairness metrics.", 174, 484, 342, 34, {
    size: 15,
    color: C.ink,
    face: C.title,
    bold: true,
  });

  box(slide, ctx, 698, 426, 438, 110, { fill: C.panel, stroke: C.gold });
  text(slide, ctx, "What I am not claiming yet", 728, 452, 220, 20, { size: 12, color: C.gold, bold: true });
  text(slide, ctx, "These are early prototype checks, not final research results or final conclusions.", 728, 484, 342, 34, {
    size: 15,
    color: C.ink,
    face: C.title,
    bold: true,
  });

  footer(slide, ctx, 7, "Source: user screenshots; preliminary batch summary");
  return slide;
}
