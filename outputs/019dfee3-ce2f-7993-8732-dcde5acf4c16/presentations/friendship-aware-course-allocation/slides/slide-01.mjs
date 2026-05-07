import { S, bg, box, footer, kicker, metric, rect, subtitle, text, title, arrowText } from "./common.mjs";

export async function slide01(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Course allocation with friendships");
  title(slide, ctx, "Когда курсы выбирают вместе: friendship-aware course allocation", {
    y: 116,
    w: 760,
    h: 142,
    size: 44,
  });
  subtitle(
    slide,
    ctx,
    "Расширение HBS-style snake draft: индивидуальные предпочтения студентов дополняются направленными отношениями дружбы и post-allocation local search.",
    62,
    282,
    700,
    52,
    { size: 16 },
  );

  rect(slide, ctx, 842, 96, 320, 420, S.dark);
  text(slide, ctx, "Core idea", 872, 130, 250, 24, { size: 11, color: "#C7D7EA", bold: true });
  text(slide, ctx, "allocation becomes\nsocially coupled", 872, 168, 246, 82, {
    size: 29,
    color: S.white,
    face: S.titleFont,
    bold: true,
  });
  text(
    slide,
    ctx,
    "A student's utility for a course depends partly on whether relevant friends are already assigned to that same course.",
    872,
    282,
    246,
    74,
    { size: 14, color: "#D9E2EF" },
  );
  formula(slide, ctx, "U = individual value + social term", 872, 392, 236, 64);

  const y = 424;
  metric(slide, ctx, "01", "Directed friendship", "asymmetric, course-specific", 64, y, { color: S.teal });
  metric(slide, ctx, "02", "Reactive utility", "only allocated friends count", 318, y, { color: S.berry });
  metric(slide, ctx, "03", "Local search", "swap, drop-add, hybrid", 574, y, { color: S.gold });

  box(slide, ctx, 102, 562, 980, 58, { stroke: S.faint });
  text(slide, ctx, "Research thesis", 128, 576, 116, 20, { size: 10, color: S.teal, bold: true });
  text(
    slide,
    ctx,
    "Friendship relations can be modeled as a formal social preference term, and their effect can be measured through welfare, inequality, and overlap statistics.",
    260,
    574,
    780,
    28,
    { size: 15, color: S.ink, face: S.titleFont, bold: true },
  );

  footer(slide, ctx, 1, "Sources: README.md; course_allocation_abstract_review.txt");
  return slide;
}

function formula(slide, ctx, value, x, y, w, h) {
  box(slide, ctx, x, y, w, h, { fill: "#223044", stroke: "#41516A" });
  text(slide, ctx, value, x + 18, y + 18, w - 36, h - 28, {
    size: 18,
    color: S.gold2,
    face: S.titleFont,
    bold: true,
    align: "center",
  });
}
