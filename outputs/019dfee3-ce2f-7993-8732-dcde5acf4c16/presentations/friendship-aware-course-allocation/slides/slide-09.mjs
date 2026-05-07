import { S, arrowText, bg, box, footer, kicker, metric, rect, stepNode, text, title } from "./common.mjs";

export async function slide09(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Evaluation design");
  title(slide, ctx, "Evaluation asks three questions: welfare, fairness, and social satisfaction.", {
    w: 940,
    h: 90,
    size: 33,
  });

  const y = 232;
  stepNode(slide, ctx, 1, "Synthetic inputs", "Table 1 rankings, Table 2 directed friends, Table 3 lambda.", 78, y, 224, 120, {
    numColor: S.blue,
  });
  arrowText(slide, ctx, 316, y + 48, 58, S.teal);
  stepNode(slide, ctx, 2, "Deterministic run", "Seeded draft plus post-grid: 0, 1, 5, 10, 20.", 388, y, 230, 120, {
    numColor: S.teal,
  });
  arrowText(slide, ctx, 632, y + 48, 58, S.berry);
  stepNode(slide, ctx, 3, "Mode sweep", "swap, drop-add, hybrid; global and personal objectives.", 704, y, 224, 120, {
    numColor: S.berry,
  });
  arrowText(slide, ctx, 944, y + 48, 58, S.gold);
  stepNode(slide, ctx, 4, "Metrics", "Total utility, Gini, ranks, friend overlap, fill rates.", 1016, y, 182, 120, {
    numColor: S.gold,
    labelSize: 13,
    bodySize: 9.2,
  });

  box(slide, ctx, 84, 430, 1092, 98, { fill: "#FFFCF4", stroke: S.faint });
  metric(slide, ctx, "200", "students", "scenario A_200x8", 126, 456, { color: S.blue, w: 130 });
  metric(slide, ctx, "8", "courses", "capacity 80", 348, 456, { color: S.teal, w: 130 });
  metric(slide, ctx, "10", "seeds", "11 through 20", 570, 456, { color: S.berry, w: 130 });
  metric(slide, ctx, "5", "post levels", "0/1/5/10/20", 792, 456, { color: S.gold, w: 130 });
  text(
    slide,
    ctx,
    "Reported result slides use saved aggregate evidence from the local SQLite experiment database.",
    982,
    468,
    150,
    38,
    { size: 10.5, color: S.muted, align: "center" },
  );

  footer(slide, ctx, 9, "Source: results/experiments/experiments.sqlite; README.md experiment sweep");
  return slide;
}
