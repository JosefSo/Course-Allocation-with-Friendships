import { S, DATA, bg, box, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide12(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Result 3: trade-off");
  title(slide, ctx, "The social gain is not free: rank satisfaction and inequality move in the opposite direction.", {
    w: 1040,
    h: 92,
    size: 32,
  });

  pairMetric(
    slide,
    ctx,
    "Average assigned position",
    "lower is better",
    "2.186",
    "2.434",
    "worse rank quality",
    82,
    234,
    S.blue,
    S.berry,
  );
  pairMetric(
    slide,
    ctx,
    "Share of top-3 assignments",
    "higher is better",
    "87.2%",
    "79.6%",
    "individual preference loss",
    456,
    234,
    S.teal,
    S.berry,
  );
  pairMetric(
    slide,
    ctx,
    "Gini total norm",
    "lower is more equal",
    "0.052",
    "0.056",
    "slightly more unequal",
    830,
    234,
    S.gold,
    S.berry,
  );

  rect(slide, ctx, 160, 534, 960, 48, S.dark);
  text(
    slide,
    ctx,
    "Interpretation: the mechanism exposes a real design question, not just an algorithmic win. Social satisfaction, individual rank quality, and fairness must be reported together.",
    196,
    548,
    888,
    18,
    { size: 13, color: S.white, face: S.titleFont, bold: true, align: "center" },
  );

  footer(slide, ctx, 12, "Source: experiments.sqlite aggregate metrics, no-post vs hybrid-global post=5");
  return slide;
}

function pairMetric(slide, ctx, label, sub, before, after, note, x, y, c1, c2) {
  box(slide, ctx, x, y, 312, 236, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, label, x + 24, y + 22, 238, 24, { size: 16, color: S.ink, face: S.titleFont, bold: true });
  text(slide, ctx, sub, x + 24, y + 50, 180, 18, { size: 9.5, color: S.muted, bold: true });
  text(slide, ctx, before, x + 34, y + 104, 96, 42, { size: 28, color: c1, face: S.titleFont, bold: true, align: "center" });
  text(slide, ctx, "baseline", x + 34, y + 150, 96, 16, { size: 9, color: S.muted, align: "center", bold: true });
  text(slide, ctx, "→", x + 140, y + 114, 32, 24, { size: 20, color: S.muted, bold: true, align: "center" });
  text(slide, ctx, after, x + 184, y + 104, 96, 42, { size: 28, color: c2, face: S.titleFont, bold: true, align: "center" });
  text(slide, ctx, "hybrid-global", x + 178, y + 150, 110, 16, { size: 9, color: S.muted, align: "center", bold: true });
  rect(slide, ctx, x + 32, y + 188, 248, 1, S.faint);
  text(slide, ctx, note, x + 34, y + 202, 244, 18, { size: 11, color: c2, bold: true, align: "center" });
}
