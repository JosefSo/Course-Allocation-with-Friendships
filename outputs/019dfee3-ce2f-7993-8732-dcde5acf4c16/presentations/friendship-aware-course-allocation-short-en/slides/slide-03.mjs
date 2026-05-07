import { C, arrow, bg, box, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Formal model");
  title(slide, ctx, "Utility combines course rankings, directed friendship preferences, and a social weight.", {
    w: 1000,
    h: 88,
    size: 32,
  });

  input(slide, ctx, "Table 1", "individual course\nranking and score", 82, 234, C.blue);
  arrow(slide, ctx, 284, 296, 62, C.teal);
  input(slide, ctx, "Table 2", "A wants friend B\nin course c", 372, 234, C.berry);
  arrow(slide, ctx, 574, 296, 62, C.teal);
  input(slide, ctx, "Table 3", "student-specific\nlambda in [0,1]", 662, 234, C.teal);

  box(slide, ctx, 890, 214, 272, 250, { fill: C.dark, stroke: C.dark });
  text(slide, ctx, "Total utility", 920, 244, 150, 20, { size: 11, color: "#C7D7EA", bold: true });
  text(slide, ctx, "U(s,c) = (1 - lambda_s) Base(s,c) + lambda_s FriendBonusNorm(s,c)", 920, 292, 210, 82, {
    size: 17,
    color: C.white,
    face: C.title,
    bold: true,
  });
  text(slide, ctx, "lambda_s controls the individual-social trade-off.", 920, 400, 204, 30, {
    size: 12,
    color: "#D9E2EF",
  });

  box(slide, ctx, 150, 510, 880, 58, { fill: C.panel, stroke: C.faint });
  text(slide, ctx, "Key modeling choice", 178, 526, 158, 18, { size: 10, color: C.teal, bold: true });
  text(slide, ctx, "The friendship relation is directed and course-specific: A -> B for course c need not imply B -> A.", 354, 523, 620, 22, {
    size: 14.5,
    color: C.ink,
    face: C.title,
    bold: true,
  });

  footer(slide, ctx, 3, "Source: README.md mathematical model and input format");
  return slide;
}

function input(slide, ctx, label, body, x, y, color) {
  box(slide, ctx, x, y, 174, 126, { fill: C.panel, stroke: color });
  rect(slide, ctx, x + 20, y + 22, 44, 28, color);
  text(slide, ctx, label, x + 76, y + 26, 76, 18, { size: 13, color: C.ink, bold: true });
  text(slide, ctx, body, x + 24, y + 76, 126, 34, { size: 11, color: C.muted, align: "center" });
}
