import { C, bg, box, footer, kicker, metric, miniTable, rect, rows, text, title } from "./common.mjs";

export async function slide05(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Experiment design");
  title(slide, ctx, "The batch compares six improvement modes across 180 deterministic runs.", {
    w: 960,
    h: 88,
    size: 33,
  });

  box(slide, ctx, 86, 216, 1092, 98, { fill: C.panel, stroke: C.faint });
  metric(slide, ctx, "30", "runs per mode", 132, 242, { color: C.blue });
  metric(slide, ctx, "20-49", "seeds", 356, 242, { color: C.teal });
  metric(slide, ctx, "6", "workers", 594, 242, { color: C.gold });
  metric(slide, ctx, "180", "completed runs", 812, 242, { color: C.berry });

  const tableRows = rows.map((r) => [
    r.mode,
    r.avgU.toFixed(3),
    r.avgGTotal.toFixed(6),
    r.avgGBase.toFixed(6),
  ]);
  const hybridIndex = tableRows.findIndex((r) => r[0] === "hybrid-global");
  tableRows[hybridIndex].bold = true;
  tableRows[hybridIndex].color = C.teal;
  miniTable(
    slide,
    ctx,
    150,
    372,
    ["Mode", "Avg U", "Avg G_total", "Avg G_base"],
    tableRows,
    [250, 150, 170, 170],
    { rowH: 36 },
  );

  rect(slide, ctx, 892, 396, 220, 116, C.dark);
  text(slide, ctx, "Reading rule", 922, 422, 140, 18, { size: 11, color: "#C7D7EA", bold: true });
  text(slide, ctx, "Higher Avg U is better. Lower Gini is more equal.", 922, 456, 158, 36, {
    size: 13.5,
    color: C.white,
    face: C.title,
    bold: true,
    align: "center",
  });

  footer(slide, ctx, 5, "Source: user screenshots, seeds 20-49");
  return slide;
}
