import { S, arrowText, bg, box, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide13(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Reproducible implementation");
  title(slide, ctx, "The system is designed as a reproducible mechanism experiment.", {
    w: 900,
    h: 86,
    size: 34,
  });

  module(slide, ctx, "CSV inputs", "schema validation\nTable 1 / 2 / 3", 88, 246, S.blue);
  arrowText(slide, ctx, 294, 306, 70, S.teal);
  module(slide, ctx, "Config", "seed, capacity,\nb, post mode", 386, 246, S.teal);
  arrowText(slide, ctx, 592, 306, 70, S.berry);
  module(slide, ctx, "Engine", "draft + local search\nfull utility audit", 684, 246, S.berry);
  arrowText(slide, ctx, 890, 306, 70, S.gold);
  module(slide, ctx, "Outputs", "allocation, post log,\nsummary, metrics", 982, 246, S.gold);

  box(slide, ctx, 154, 468, 972, 72, { fill: "#FFFCF4", stroke: S.faint });
  fact(slide, ctx, "Seeded RNG", "same seed, same allocation", 190, 490, S.blue);
  fact(slide, ctx, "No external deps", "standard library only", 444, 490, S.teal);
  fact(slide, ctx, "Tests", "utility, tie-breaks, metrics, API", 684, 490, S.berry);
  fact(slide, ctx, "Audit trail", "every pick and post move logged", 920, 490, S.gold);

  footer(slide, ctx, 13, "Source: README.md features, output files, testing");
  return slide;
}

function module(slide, ctx, label, body, x, y, color) {
  box(slide, ctx, x, y, 178, 138, { fill: "#FFFCF4", stroke: color });
  rect(slide, ctx, x + 22, y + 22, 44, 30, color);
  text(slide, ctx, label, x + 76, y + 26, 82, 20, { size: 14, color: S.ink, face: S.titleFont, bold: true });
  text(slide, ctx, body, x + 26, y + 78, 126, 36, { size: 11, color: S.muted, align: "center" });
}

function fact(slide, ctx, label, body, x, y, color) {
  rect(slide, ctx, x, y + 2, 4, 38, color);
  text(slide, ctx, label, x + 16, y, 130, 18, { size: 11, color, bold: true });
  text(slide, ctx, body, x + 16, y + 20, 160, 16, { size: 9.5, color: S.muted });
}
