import { C, bg, box, footer, kicker, metric, rect, text, title } from "./common.mjs";

export async function slide01(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Friendship-aware course allocation");
  title(slide, ctx, "Course allocation becomes a social mechanism when friends enter the utility model.", {
    y: 112,
    w: 760,
    h: 142,
    size: 42,
  });
  text(
    slide,
    ctx,
    "A deterministic HBS-style draft is extended with directed friendship preferences and a post-allocation improvement stage.",
    62,
    286,
    650,
    48,
    { size: 16, color: C.muted },
  );

  rect(slide, ctx, 820, 104, 330, 360, C.dark);
  text(slide, ctx, "Main empirical result", 852, 138, 230, 18, { size: 11, color: "#C7D7EA", bold: true });
  text(slide, ctx, "hybrid-global wins on average utility", 852, 178, 242, 102, {
    size: 31,
    color: C.white,
    face: C.title,
    bold: true,
  });
  text(slide, ctx, "Avg U = 365.025017 across 30 runs per mode.", 852, 312, 230, 36, {
    size: 13.5,
    color: "#D9E2EF",
  });
  box(slide, ctx, 852, 384, 232, 46, { fill: C.dark2, stroke: "#41516A" });
  text(slide, ctx, "Shortest version: model -> method -> evidence", 870, 398, 196, 18, {
    size: 12,
    color: "#F1D49D",
    bold: true,
    align: "center",
  });

  metric(slide, ctx, "180", "completed runs", 80, 438, { color: C.blue });
  metric(slide, ctx, "6", "allocation modes", 314, 438, { color: C.teal });
  metric(slide, ctx, "20-49", "seed range", 548, 438, { color: C.gold, w: 170 });

  box(slide, ctx, 110, 558, 930, 54, { fill: C.panel, stroke: C.faint });
  text(slide, ctx, "Thesis", 132, 574, 72, 18, { size: 10, color: C.teal, bold: true });
  text(slide, ctx, "Friendship is not just contextual information; it changes the objective landscape of course allocation.", 224, 571, 770, 22, {
    size: 15,
    color: C.ink,
    face: C.title,
    bold: true,
  });

  footer(slide, ctx, 1, "Sources: README.md; user result screenshots");
  return slide;
}
