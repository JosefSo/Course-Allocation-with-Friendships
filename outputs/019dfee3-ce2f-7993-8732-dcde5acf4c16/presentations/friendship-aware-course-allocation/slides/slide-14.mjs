import { S, bg, box, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide14(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx, true);
  kicker(slide, ctx, "Contribution", { dark: true, color: S.gold2 });
  title(slide, ctx, "The contribution is a testable bridge between mechanism design and social preference modeling.", {
    w: 1000,
    h: 110,
    size: 36,
    dark: true,
  });

  contribution(slide, ctx, "Model", "Directed friendship preferences enter utility through a student-specific social weight λ_s.", 92, 260, S.teal2);
  contribution(slide, ctx, "Mechanism", "A deterministic HBS-style snake draft remains feasible and reproducible while using reactive social utility.", 456, 260, S.gold2);
  contribution(slide, ctx, "Experiment", "Post-allocation local search reveals welfare, friendship-overlap, rank, and fairness trade-offs.", 820, 260, S.berry2);

  rect(slide, ctx, 142, 520, 996, 1, "#41516A");
  text(slide, ctx, "Next research questions", 160, 548, 210, 20, { size: 12, color: S.gold2, bold: true, dark: true });
  text(
    slide,
    ctx,
    "strategic friendship reports  ·  real enrollment data  ·  welfare/fairness frontier  ·  theoretical properties of reactive social mechanisms",
    386,
    546,
    702,
    24,
    { size: 14, color: "#D9E2EF", face: S.titleFont, bold: true, dark: true },
  );

  footer(slide, ctx, 14, "Synthesis from local project sources", { dark: true });
  return slide;
}

function contribution(slide, ctx, label, body, x, y, color) {
  box(slide, ctx, x, y, 286, 176, { fill: "#223044", stroke: "#41516A" });
  text(slide, ctx, label, x + 24, y + 24, 150, 28, { size: 22, color, face: S.titleFont, bold: true, dark: true });
  text(slide, ctx, body, x + 24, y + 72, 226, 72, { size: 14, color: "#FFFFFF", face: S.titleFont, bold: true, dark: true });
}
