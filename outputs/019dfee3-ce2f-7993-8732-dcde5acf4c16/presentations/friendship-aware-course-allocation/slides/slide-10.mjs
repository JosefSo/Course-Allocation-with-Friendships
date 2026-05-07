import { S, DATA, bg, box, footer, kicker, rect, text, title, vrule } from "./common.mjs";

export async function slide10(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Result 1: welfare");
  title(slide, ctx, "Hybrid-global captures most of the welfare gain within five iterations.", {
    w: 930,
    h: 90,
    size: 33,
  });

  text(slide, ctx, "Mean total-utility change vs. no-post baseline", 86, 202, 430, 22, {
    size: 12,
    color: S.muted,
    bold: true,
  });
  const bars = [
    { label: "hybrid-global, post=5", value: DATA.summary.hybridPct, color: S.teal, note: "+3.63%" },
    { label: "swap-global, post=20", value: DATA.summary.swapPct, color: S.blue, note: "+2.21%" },
    { label: "drop-add-global, post=20", value: DATA.summary.dropAddPct, color: S.gold, note: "+0.26%" },
    { label: "hybrid-personal, post=20", value: DATA.summary.hybridPersonalPct, color: S.berry, note: "-0.39%" },
  ];
  bars.forEach((d, i) => gainBar(slide, ctx, d, 96, 252 + i * 64));

  box(slide, ctx, 734, 222, 370, 270, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, "Mechanistic reading", 766, 248, 190, 20, { size: 12, color: S.teal, bold: true });
  text(slide, ctx, "371.31", 768, 294, 132, 42, { size: 34, color: S.ink, face: S.titleFont, bold: true });
  text(slide, ctx, "baseline mean total utility", 770, 338, 180, 18, { size: 10, color: S.muted, bold: true });
  text(slide, ctx, "384.80", 942, 294, 132, 42, { size: 34, color: S.teal, face: S.titleFont, bold: true });
  text(slide, ctx, "hybrid-global at post=5", 944, 338, 170, 18, { size: 10, color: S.muted, bold: true });
  rect(slide, ctx, 770, 388, 292, 1, S.faint);
  text(
    slide,
    ctx,
    "Global hybrid search uses both spare-capacity add/drop moves and swaps, so it can escape path dependence faster than a single operator.",
    770,
    418,
    290,
    44,
    { size: 12.5, color: S.ink, face: S.titleFont, bold: true },
  );

  footer(slide, ctx, 10, "Source: results/experiments/experiments.sqlite, scenario A_200x8, seeds 11-20");
  return slide;
}

function gainBar(slide, ctx, item, x, y) {
  const labelW = 230;
  const trackW = 278;
  const zero = x + labelW + 52;
  const scale = 60;
  text(slide, ctx, item.label, x, y - 1, labelW, 22, { size: 12, color: S.ink, bold: true });
  rect(slide, ctx, x + labelW, y + 6, trackW, 10, S.faint2);
  vrule(slide, ctx, zero, y - 4, 30, S.muted, 1);
  if (item.value >= 0) {
    rect(slide, ctx, zero, y + 3, Math.max(3, item.value * scale), 16, item.color);
  } else {
    rect(slide, ctx, zero + item.value * scale, y + 3, Math.max(3, Math.abs(item.value) * scale), 16, item.color);
  }
  text(slide, ctx, item.note, x + labelW + trackW + 18, y - 4, 76, 24, {
    size: 14,
    color: item.color,
    bold: true,
    align: "right",
  });
}
