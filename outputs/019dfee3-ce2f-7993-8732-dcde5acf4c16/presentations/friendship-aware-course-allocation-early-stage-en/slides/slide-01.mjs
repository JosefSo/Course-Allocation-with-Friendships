import { C, bg, box, footer, kicker, metric, rect, text, title } from "./common.mjs";

export async function slide01(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Early-stage research");
  title(slide, ctx, "Course Allocation\nwith Friendships", {
    y: 118,
    w: 720,
    h: 118,
    size: 46,
  });
  text(
    slide,
    ctx,
    "A first framework for adding friendship relations to course allocation.",
    62,
    266,
    680,
    34,
    { size: 21, color: C.muted, face: C.title, bold: true },
  );
  text(
    slide,
    ctx,
    "This talk is about the research direction, the modeling idea, and the prototype built so far — not final empirical conclusions.",
    64,
    334,
    640,
    54,
    { size: 16, color: C.muted },
  );

  rect(slide, ctx, 814, 102, 328, 364, C.dark);
  text(slide, ctx, "Core question", 846, 138, 150, 18, { size: 11, color: "#C7D7EA", bold: true });
  text(slide, ctx, "How can friendship enter an allocation model?", 846, 184, 232, 112, {
    size: 29,
    color: C.white,
    face: C.title,
    bold: true,
  });
  box(slide, ctx, 846, 372, 232, 54, { fill: C.dark2, stroke: "#41516A" });
  text(slide, ctx, "concept -> formula -> prototype", 864, 389, 196, 18, {
    size: 12,
    color: "#F1D49D",
    bold: true,
    align: "center",
  });

  metric(slide, ctx, "1", "modeling idea", "friendship as utility", 88, 492, C.teal);
  metric(slide, ctx, "1", "prototype", "CSV -> allocation -> metrics", 350, 492, C.blue);
  metric(slide, ctx, "180", "test runs", "pipeline validation", 612, 492, C.gold);

  footer(slide, ctx, 1, "Positioning: early-stage research presentation");
  return slide;
}
