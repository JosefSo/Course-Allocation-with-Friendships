import { C, arrow, bg, box, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide06(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Prototype");
  title(slide, ctx, "The current achievement is a working research pipeline.", {
    w: 900,
    h: 88,
    size: 36,
  });

  node(slide, ctx, "Inputs", "course preferences\nfriend preferences\nlambda values", 96, 244, C.blue);
  arrow(slide, ctx, 304, 314, 72, C.teal);
  node(slide, ctx, "Model", "utility calculation\nwith social term", 400, 244, C.teal);
  arrow(slide, ctx, 608, 314, 72, C.berry);
  node(slide, ctx, "Allocation", "prototype mechanism\nand logs", 704, 244, C.berry);
  arrow(slide, ctx, 912, 314, 72, C.gold);
  node(slide, ctx, "Metrics", "utility\nfriend overlap\nGini index", 1008, 244, C.gold);

  box(slide, ctx, 164, 510, 952, 62, { fill: C.panel, stroke: C.faint });
  text(slide, ctx, "How to present this", 194, 529, 150, 18, { size: 10, color: C.teal, bold: true });
  text(slide, ctx, "At this stage, the prototype is mainly a way to make the research question testable.", 362, 524, 694, 24, {
    size: 16,
    color: C.ink,
    face: C.title,
    bold: true,
    align: "center",
  });

  footer(slide, ctx, 6, "Source: README.md implementation structure and output files");
  return slide;
}

function node(slide, ctx, label, body, x, y, color) {
  box(slide, ctx, x, y, 176, 152, { fill: C.panel, stroke: color });
  rect(slide, ctx, x + 22, y + 22, 42, 30, color);
  text(slide, ctx, label, x + 76, y + 25, 78, 20, { size: 15, color: C.ink, face: C.title, bold: true });
  text(slide, ctx, body, x + 26, y + 82, 124, 42, { size: 11, color: C.muted, align: "center" });
}
