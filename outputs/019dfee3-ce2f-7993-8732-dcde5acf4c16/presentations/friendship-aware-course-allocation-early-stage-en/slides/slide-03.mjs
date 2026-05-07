import { C, bg, box, conceptBox, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Research framing");
  title(slide, ctx, "The project extends course allocation with a social preference layer.", {
    w: 930,
    h: 88,
    size: 35,
  });

  conceptBox(
    slide,
    ctx,
    "BASE PROBLEM",
    "Assign students to feasible bundles of course seats under capacity constraints.",
    90,
    232,
    330,
    178,
    C.blue,
  );
  conceptBox(
    slide,
    ctx,
    "MY EXTENSION",
    "Add directed, course-specific friendship preferences as part of utility.",
    476,
    232,
    330,
    178,
    C.teal,
  );
  conceptBox(
    slide,
    ctx,
    "CURRENT STAGE",
    "Build the model and prototype first; use experiments to understand behavior later.",
    862,
    232,
    330,
    178,
    C.gold,
  );

  box(slide, ctx, 176, 506, 928, 60, { fill: C.panel, stroke: C.faint });
  text(slide, ctx, "Research question", 204, 524, 140, 18, { size: 10, color: C.teal, bold: true });
  text(slide, ctx, "Can friendship-aware utility be integrated into course allocation in a clear, reproducible way?", 362, 520, 682, 24, {
    size: 15,
    color: C.ink,
    face: C.title,
    bold: true,
    align: "center",
  });

  footer(slide, ctx, 3, "Source framing: course allocation as one-sided combinatorial assignment");
  return slide;
}
