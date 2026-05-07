import { C, bg, box, footer, kicker, text, title } from "./common.mjs";

export async function slide08(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx, true);
  kicker(slide, ctx, "Next steps", { dark: true, color: "#F1D49D" });
  title(slide, ctx, "The next stage is to refine the model and evaluate it carefully.", {
    w: 1040,
    h: 96,
    size: 38,
    dark: true,
  });

  next(slide, ctx, "1", "Model refinement", "Decide how friendship strength, direction, and course context should be represented.", 104, 268, "#BFE3DC");
  next(slide, ctx, "2", "Better evaluation", "Compare utility, friendship overlap, and Gini index without overclaiming early results.", 456, 268, "#F1D49D");
  next(slide, ctx, "3", "Research feedback", "Use this stage to clarify assumptions, definitions, and the most interesting questions.", 808, 268, "#E9B8C6");

  box(slide, ctx, 172, 534, 936, 54, { fill: C.dark2, stroke: "#41516A" });
  text(slide, ctx, "The goal for now is not to prove the final answer; it is to build a clean framework that can support serious analysis.", 214, 550, 852, 18, {
    size: 14,
    color: C.white,
    face: C.title,
    bold: true,
    align: "center",
    dark: true,
  });

  footer(slide, ctx, 8, "Research-in-progress close", { dark: true });
  return slide;
}

function next(slide, ctx, n, label, body, x, y, color) {
  box(slide, ctx, x, y, 284, 176, { fill: C.dark2, stroke: "#41516A" });
  text(slide, ctx, n, x + 24, y + 24, 38, 26, { size: 22, color, face: C.title, bold: true, dark: true });
  text(slide, ctx, label, x + 72, y + 26, 166, 24, { size: 19, color, face: C.title, bold: true, dark: true });
  text(slide, ctx, body, x + 28, y + 78, 220, 62, { size: 13.5, color: C.white, face: C.title, bold: true, dark: true });
}
