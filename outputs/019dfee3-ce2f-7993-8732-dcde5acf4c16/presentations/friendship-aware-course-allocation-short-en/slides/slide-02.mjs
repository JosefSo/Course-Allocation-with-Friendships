import { C, bg, callout, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide02(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Research gap");
  title(slide, ctx, "Classical course allocation usually treats students as independent agents.", {
    w: 940,
    h: 88,
    size: 34,
  });

  callout(
    slide,
    ctx,
    "CLASSICAL PROBLEM",
    "Assign feasible bundles of indivisible course seats under capacity constraints.",
    88,
    238,
    318,
    180,
    C.blue,
  );
  callout(
    slide,
    ctx,
    "MISSING EXTERNALITY",
    "Students may care not only about courses, but also about attending them with friends.",
    482,
    238,
    318,
    180,
    C.berry,
  );
  callout(
    slide,
    ctx,
    "PROJECT MOVE",
    "Add a directed friendship term to utility, then evaluate welfare and fairness trade-offs.",
    876,
    238,
    318,
    180,
    C.teal,
  );

  rect(slide, ctx, 174, 516, 932, 48, C.dark);
  text(slide, ctx, "Academic framing: this is a one-sided combinatorial assignment problem with social preferences.", 208, 530, 864, 18, {
    size: 14,
    color: C.white,
    face: C.title,
    bold: true,
    align: "center",
  });

  footer(slide, ctx, 2, "Source: course_allocation_abstract_review.txt");
  return slide;
}
