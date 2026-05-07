import { C, bg, box, footer, kicker, pill, rect, text, title } from "./common.mjs";

export async function slide05(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Utility model");
  title(slide, ctx, "The model combines course preference and friendship preference.", {
    w: 940,
    h: 88,
    size: 35,
  });

  box(slide, ctx, 118, 224, 1044, 102, { fill: C.panel, stroke: C.teal });
  text(slide, ctx, "Utility(student, course)", 154, 254, 230, 24, {
    size: 20,
    color: C.teal,
    face: C.title,
    bold: true,
  });
  text(slide, ctx, "=", 400, 254, 34, 24, { size: 22, color: C.muted, bold: true, align: "center" });
  text(slide, ctx, "course value", 448, 254, 180, 24, { size: 22, color: C.blue, face: C.title, bold: true });
  text(slide, ctx, "+", 640, 254, 34, 24, { size: 22, color: C.muted, bold: true, align: "center" });
  text(slide, ctx, "friendship value", 688, 254, 220, 24, { size: 22, color: C.berry, face: C.title, bold: true });
  text(slide, ctx, "weighted by lambda", 924, 258, 164, 18, { size: 13, color: C.gold, bold: true });

  box(slide, ctx, 150, 392, 280, 122, { fill: C.panel, stroke: C.blue });
  text(slide, ctx, "Course value", 178, 416, 140, 22, { size: 17, color: C.blue, face: C.title, bold: true });
  text(slide, ctx, "comes from the student's ranking of courses.", 178, 456, 198, 38, { size: 13, color: C.muted });

  box(slide, ctx, 500, 392, 280, 122, { fill: C.panel, stroke: C.berry });
  text(slide, ctx, "Friendship value", 528, 416, 170, 22, { size: 17, color: C.berry, face: C.title, bold: true });
  text(slide, ctx, "comes from course-specific friend preferences.", 528, 456, 198, 38, { size: 13, color: C.muted });

  box(slide, ctx, 850, 392, 280, 122, { fill: C.panel, stroke: C.gold });
  text(slide, ctx, "Lambda", 878, 416, 120, 22, { size: 17, color: C.gold, face: C.title, bold: true });
  text(slide, ctx, "controls how much social preference matters.", 878, 456, 198, 38, { size: 13, color: C.muted });

  pill(slide, ctx, "lambda = 0: only courses", 252, 560, 190, C.blue);
  pill(slide, ctx, "lambda = 0.5: mixed utility", 548, 560, 200, C.teal);
  pill(slide, ctx, "lambda = 1: only social term", 850, 560, 210, C.berry);

  footer(slide, ctx, 5, "Source: README.md utility model");
  return slide;
}
