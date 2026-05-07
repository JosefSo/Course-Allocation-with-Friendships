import { S, DATA, bg, box, footer, kicker, rect, text, title, vBars } from "./common.mjs";

export async function slide11(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Result 2: social satisfaction");
  title(slide, ctx, "The welfare gain is social: average friendship overlap rises by about one quarter.", {
    w: 950,
    h: 90,
    size: 33,
  });

  box(slide, ctx, 92, 218, 520, 324, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, "Avg. friend overlaps per student", 124, 242, 260, 22, {
    size: 12,
    color: S.muted,
    bold: true,
  });
  vBars(
    slide,
    ctx,
    196,
    304,
    276,
    150,
    [
      { label: "no post", value: DATA.summary.friendBase, valueLabel: "3.71", color: S.blue },
      { label: "hybrid-global\npost=5", value: DATA.summary.friendHybrid, valueLabel: "4.70", color: S.teal },
    ],
    { min: 3, max: 5, gap: 86, valueSize: 16, labelSize: 11 },
  );
  rect(slide, ctx, 404, 276, 126, 42, S.dark);
  text(slide, ctx, "+26.4%", 418, 286, 98, 20, { size: 18, color: S.gold2, face: S.titleFont, bold: true, align: "center" });

  box(slide, ctx, 700, 218, 406, 324, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, "What the metric captures", 732, 244, 220, 20, { size: 12, color: S.teal, bold: true });
  point(slide, ctx, "1", "A directed relation A → B is counted only for the course context where A expressed it.", 740, 292, S.berry);
  point(slide, ctx, "2", "An overlap occurs when A receives course c and B also receives c.", 740, 368, S.teal);
  point(slide, ctx, "3", "The increase therefore reflects more socially aligned assignments, not just more filled seats.", 740, 444, S.gold);

  footer(slide, ctx, 11, "Source: experiments.sqlite aggregate metrics, A_200x8");
  return slide;
}

function point(slide, ctx, n, body, x, y, color) {
  rect(slide, ctx, x, y, 34, 34, color);
  text(slide, ctx, n, x, y + 8, 34, 14, { size: 11, color: S.white, bold: true, align: "center" });
  text(slide, ctx, body, x + 52, y - 2, 278, 42, { size: 12, color: S.ink, face: S.titleFont, bold: true });
}
