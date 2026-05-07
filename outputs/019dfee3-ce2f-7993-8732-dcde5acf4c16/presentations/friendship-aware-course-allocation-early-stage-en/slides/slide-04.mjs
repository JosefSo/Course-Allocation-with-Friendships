import { C, arrow, bg, box, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide04(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "From friendship to math");
  title(slide, ctx, "The key step is translating a friendship statement into a course-specific value.", {
    w: 1000,
    h: 88,
    size: 33,
  });

  step(slide, ctx, "1", "Student A", "expresses a preference", 98, 252, C.blue);
  arrow(slide, ctx, 314, 320, 66, C.teal);
  step(slide, ctx, "2", "Friend B", "is relevant for A", 404, 252, C.berry);
  arrow(slide, ctx, 620, 320, 66, C.teal);
  step(slide, ctx, "3", "Course C", "is the context", 710, 252, C.gold);
  arrow(slide, ctx, 926, 320, 66, C.teal);
  step(slide, ctx, "4", "Social value", "is added to utility", 1016, 252, C.teal);

  box(slide, ctx, 160, 494, 960, 68, { fill: C.panel, stroke: C.faint });
  text(slide, ctx, "Plain-language meaning", 190, 514, 188, 18, { size: 10, color: C.teal, bold: true });
  text(slide, ctx, "A says: being in course C is more valuable to me if B is also in course C.", 396, 509, 664, 28, {
    size: 18,
    color: C.ink,
    face: C.title,
    bold: true,
    align: "center",
  });

  footer(slide, ctx, 4, "Source: README.md directed friend preference semantics");
  return slide;
}

function step(slide, ctx, n, label, body, x, y, color) {
  box(slide, ctx, x, y, 188, 142, { fill: C.panel, stroke: color });
  rect(slide, ctx, x + 20, y + 20, 34, 28, color);
  text(slide, ctx, n, x + 20, y + 27, 34, 14, { size: 10, color: C.white, bold: true, align: "center" });
  text(slide, ctx, label, x + 66, y + 22, 94, 24, { size: 16, color: C.ink, face: C.title, bold: true });
  text(slide, ctx, body, x + 30, y + 78, 128, 28, { size: 11.5, color: C.muted, align: "center" });
}
