import { S, arrowText, bg, box, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide06(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Draft mechanism");
  title(slide, ctx, "The HBS-style snake draft remains deterministic while utility becomes social.", {
    w: 930,
    h: 88,
    size: 33,
  });

  box(slide, ctx, 82, 210, 484, 280, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, "Snake order", 112, 234, 170, 22, { size: 12, color: S.teal, bold: true });
  round(slide, ctx, "Round 1", ["S2", "S1", "S3", "S4"], 124, 292, S.teal, false);
  round(slide, ctx, "Round 2", ["S4", "S3", "S1", "S2"], 124, 378, S.berry, true);
  text(
    slide,
    ctx,
    "The seeded permutation is fixed; odd rounds use π, even rounds reverse π. Social utility can change course choice, not the reproducibility of the order.",
    112,
    450,
    400,
    26,
    { size: 10.5, color: S.muted },
  );

  box(slide, ctx, 640, 210, 500, 280, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, "Tie-breaking chain", 670, 234, 190, 22, { size: 12, color: S.berry, bold: true });
  const steps = [
    ["max U(s,c)", S.teal],
    ["max Score", S.blue],
    ["min Position", S.gold],
    ["seeded rnd", S.berry],
    ["min CourseID", S.muted],
  ];
  steps.forEach(([label, color], i) => {
    rect(slide, ctx, 678 + i * 88, 314, 76, 46, "#FFFFFF", { line: ctx.line(color, 1) });
    text(slide, ctx, label, 684 + i * 88, 328, 64, 18, { size: 9.5, color, bold: true, align: "center" });
    if (i < steps.length - 1) arrowText(slide, ctx, 756 + i * 88, 328, 22, color);
  });
  text(
    slide,
    ctx,
    "The tolerance τ = 10^-9 prevents floating-point noise from bypassing the intended deterministic tie-break.",
    672,
    408,
    402,
    38,
    { size: 12, color: S.muted },
  );

  rect(slide, ctx, 190, 548, 900, 44, S.dark);
  text(
    slide,
    ctx,
    "Mechanism claim: the model adds social information without giving up seeded reproducibility or feasibility checks.",
    220,
    561,
    840,
    18,
    { size: 14, color: S.white, face: S.titleFont, bold: true, align: "center" },
  );

  footer(slide, ctx, 6, "Source: README.md pick rule and snake draft order");
  return slide;
}

function round(slide, ctx, label, students, x, y, color, reverse) {
  text(slide, ctx, label, x, y + 12, 70, 20, { size: 11, color, bold: true });
  students.forEach((student, i) => {
    const xx = x + 92 + i * 72;
    rect(slide, ctx, xx, y, 50, 44, i % 2 ? "#FFFFFF" : S.faint2, { line: ctx.line(color, 1) });
    text(slide, ctx, student, xx, y + 14, 50, 16, { size: 12, color: S.ink, bold: true, align: "center" });
    if (i < students.length - 1) arrowText(slide, ctx, xx + 54, y + 15, 28, color);
  });
  text(slide, ctx, reverse ? "reverse(π)" : "π", x + 398, y + 12, 70, 20, { size: 11, color: S.muted, bold: true });
}
