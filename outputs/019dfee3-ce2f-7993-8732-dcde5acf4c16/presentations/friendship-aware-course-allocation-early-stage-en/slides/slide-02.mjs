import { C, bg, box, conceptBox, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide02(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Motivation");
  title(slide, ctx, "Students may care about the course and about who takes it with them.", {
    w: 1000,
    h: 88,
    size: 35,
  });

  conceptBox(
    slide,
    ctx,
    "INDIVIDUAL VALUE",
    "How much do I want this course?",
    116,
    246,
    300,
    164,
    C.blue,
  );
  conceptBox(
    slide,
    ctx,
    "SOCIAL VALUE",
    "Would I be in this course with people I care about?",
    490,
    246,
    300,
    164,
    C.teal,
  );
  conceptBox(
    slide,
    ctx,
    "RESEARCH CHALLENGE",
    "How do we combine these two ideas without leaving the allocation framework?",
    864,
    246,
    300,
    164,
    C.berry,
  );

  rect(slide, ctx, 194, 514, 892, 48, C.dark);
  text(
    slide,
    ctx,
    "The novelty is not that students have friends; the novelty is treating friendship as structured allocation information.",
    230,
    528,
    820,
    18,
    { size: 14, color: C.white, face: C.title, bold: true, align: "center" },
  );

  footer(slide, ctx, 2, "Research motivation: social preferences in course choice");
  return slide;
}
