import { S, bg, box, footer, kicker, labelBox, rect, subtitle, text, title } from "./common.mjs";

export async function slide02(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Research gap");
  title(slide, ctx, "Классическая постановка теряет социальную внешность выбора.", {
    w: 900,
    h: 94,
    size: 36,
  });
  subtitle(
    slide,
    ctx,
    "Стандартный course allocation рассматривает студентов как независимых агентов. Но в реальном выборе курсов полезность часто зависит от того, с кем студент окажется в аудитории.",
    62,
    174,
    900,
    48,
  );

  labelBox(
    slide,
    ctx,
    "CLASSICAL BASELINE",
    "One-sided combinatorial assignment: students receive feasible bundles of indivisible course seats under capacity constraints.",
    72,
    274,
    330,
    196,
    { labelColor: S.blue, bodySize: 18 },
  );
  labelBox(
    slide,
    ctx,
    "MISSING VARIABLE",
    "Preferences are usually individual: the model observes how much a student wants a course, not whether friends also make that course valuable.",
    474,
    274,
    330,
    196,
    { labelColor: S.berry, bodySize: 18 },
  );
  labelBox(
    slide,
    ctx,
    "PROJECT EXTENSION",
    "A directed friendship term enters the utility model and is evaluated together with welfare, inequality, and social-overlap metrics.",
    876,
    274,
    330,
    196,
    { labelColor: S.teal, bodySize: 18 },
  );

  rect(slide, ctx, 92, 535, 1096, 46, S.dark);
  text(
    slide,
    ctx,
    "Main conceptual move: friendship is not a side note after allocation; it becomes part of the mechanism's utility calculation.",
    122,
    548,
    1038,
    22,
    { size: 15, color: S.white, face: S.titleFont, bold: true, align: "center" },
  );

  footer(slide, ctx, 2, "Source: course_allocation_abstract_review.txt");
  return slide;
}
