import { C, arrow, bg, box, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide04(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Mechanism");
  title(slide, ctx, "The mechanism has an initial reactive draft and a post-allocation improvement stage.", {
    w: 1000,
    h: 88,
    size: 32,
  });

  stage(slide, ctx, "1", "Seeded snake draft", "Students pick in a fixed order; even rounds reverse the order.", 92, 240, C.blue);
  arrow(slide, ctx, 336, 304, 70, C.teal);
  stage(slide, ctx, "2", "Reactive friend bonus", "Only friends already assigned to the candidate course contribute.", 430, 240, C.teal);
  arrow(slide, ctx, 674, 304, 70, C.berry);
  stage(slide, ctx, "3", "Local search", "Swap, drop-add, or hybrid moves are accepted only if the objective improves.", 768, 240, C.berry);

  box(slide, ctx, 156, 506, 968, 62, { fill: C.panel, stroke: C.faint });
  text(slide, ctx, "Why reactive?", 184, 524, 116, 18, { size: 10, color: C.teal, bold: true });
  text(slide, ctx, "It avoids circular dependence: every utility evaluation is based on the current allocation state.", 318, 520, 748, 24, {
    size: 15,
    color: C.ink,
    face: C.title,
    bold: true,
    align: "center",
  });

  footer(slide, ctx, 4, "Source: README.md reactive bonus, snake draft, and post-draft improvement");
  return slide;
}

function stage(slide, ctx, n, label, body, x, y, color) {
  box(slide, ctx, x, y, 220, 168, { fill: C.panel, stroke: color });
  rect(slide, ctx, x + 22, y + 22, 36, 30, color);
  text(slide, ctx, n, x + 22, y + 29, 36, 16, { size: 11, color: C.white, bold: true, align: "center" });
  text(slide, ctx, label, x + 72, y + 24, 120, 30, { size: 16, color: C.ink, face: C.title, bold: true });
  text(slide, ctx, body, x + 30, y + 84, 160, 50, { size: 11.5, color: C.muted, align: "center" });
}
