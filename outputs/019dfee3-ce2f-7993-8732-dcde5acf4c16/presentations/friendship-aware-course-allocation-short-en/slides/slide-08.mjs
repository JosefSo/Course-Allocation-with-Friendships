import { C, bg, box, footer, kicker, miniTable, rect, text, title } from "./common.mjs";

export async function slide08(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Trade-off");
  title(slide, ctx, "The central empirical message is a utility-fairness trade-off.", {
    w: 940,
    h: 88,
    size: 34,
  });

  const rows = [
    ["hybrid-global", "1", "5", "6"],
    ["swap-global", "2", "2", "4"],
    ["drop-add-global", "3", "1", "2"],
    ["drop-add-personal", "4", "4", "3"],
    ["swap-personal", "5", "3", "1"],
    ["hybrid-personal", "6", "6", "5"],
  ];
  rows[0].bold = true;
  rows[0].color = C.teal;
  rows[2].bold = true;
  rows[2].color = C.gold;
  miniTable(
    slide,
    ctx,
    104,
    230,
    ["Mode", "Avg U rank", "Avg G_total rank", "Avg G_base rank"],
    rows,
    [260, 140, 170, 170],
    { rowH: 38 },
  );

  box(slide, ctx, 876, 244, 268, 250, { fill: C.dark, stroke: C.dark });
  text(slide, ctx, "Takeaway", 906, 272, 130, 18, { size: 11, color: "#C7D7EA", bold: true });
  text(slide, ctx, "Hybrid-global is best if the priority is utility.", 906, 314, 198, 42, {
    size: 18,
    color: C.white,
    face: C.title,
    bold: true,
  });
  rect(slide, ctx, 906, 382, 204, 1, "#41516A");
  text(slide, ctx, "Drop-add-global is best if the priority is average total equality.", 906, 408, 198, 42, {
    size: 17,
    color: "#F1D49D",
    face: C.title,
    bold: true,
  });

  rect(slide, ctx, 178, 552, 922, 42, C.panel, { line: ctx.line(C.faint, 1) });
  text(slide, ctx, "This is exactly why the contribution is experimental: the model exposes choices that cannot be reduced to one metric.", 214, 565, 850, 16, {
    size: 13.5,
    color: C.ink,
    face: C.title,
    bold: true,
    align: "center",
  });

  footer(slide, ctx, 8, "Ranks computed from screenshot table: higher utility is better, lower Gini is better");
  return slide;
}
