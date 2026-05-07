import { C, bg, box, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide09(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx, true);
  kicker(slide, ctx, "Conclusion", { dark: true, color: "#F1D49D" });
  title(slide, ctx, "Friendship-aware allocation turns course choice into a measurable social design problem.", {
    w: 1040,
    h: 108,
    size: 36,
    dark: true,
  });

  conclusion(slide, ctx, "Model", "Directed friendship preferences enter the utility function through lambda-weighted social value.", 100, 270, "#BFE3DC");
  conclusion(slide, ctx, "Mechanism", "Reactive utility keeps each draft pick well-defined, deterministic, and feasible.", 456, 270, "#F1D49D");
  conclusion(slide, ctx, "Evidence", "Hybrid-global maximizes average utility; drop-add-global gives the lowest average total Gini.", 812, 270, "#E9B8C6");

  rect(slide, ctx, 150, 520, 980, 1, "#41516A");
  text(slide, ctx, "Next steps", 166, 548, 140, 18, { size: 12, color: "#F1D49D", bold: true, dark: true });
  text(slide, ctx, "real enrollment data  |  strategic friendship reports  |  welfare-fairness frontier  |  theoretical guarantees", 324, 546, 760, 24, {
    size: 14,
    color: "#D9E2EF",
    face: C.title,
    bold: true,
    dark: true,
  });

  footer(slide, ctx, 9, "Synthesis from project sources and latest screenshot batch", { dark: true });
  return slide;
}

function conclusion(slide, ctx, label, body, x, y, color) {
  box(slide, ctx, x, y, 280, 166, { fill: C.dark2, stroke: "#41516A" });
  text(slide, ctx, label, x + 24, y + 24, 140, 24, { size: 22, color, face: C.title, bold: true, dark: true });
  text(slide, ctx, body, x + 24, y + 72, 220, 62, { size: 14, color: C.white, face: C.title, bold: true, dark: true });
}
