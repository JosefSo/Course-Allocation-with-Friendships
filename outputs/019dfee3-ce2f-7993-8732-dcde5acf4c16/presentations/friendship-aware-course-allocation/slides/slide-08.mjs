import { S, bg, box, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide08(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Method space");
  title(slide, ctx, "The design space is three move operators crossed with two objectives.", {
    w: 900,
    h: 86,
    size: 34,
  });

  const x = 118;
  const y = 214;
  const w0 = 206;
  const w1 = 380;
  const h = 92;
  text(slide, ctx, "Move type", x, y - 36, w0, 20, { size: 11, color: S.muted, bold: true });
  header(slide, ctx, "Global welfare objective\naccept if ΔW > 0", x + w0, y - 48, w1, S.teal);
  header(slide, ctx, "Personal objective\naccept if ΔU_s > 0", x + w0 + w1, y - 48, w1, S.berry);

  row(slide, ctx, "swap", "Exchange two assigned seats between students.", "ΔW_global over feasible pair swaps", "ΔU_current over oriented swaps", x, y, w0, w1, h);
  row(slide, ctx, "drop-add", "Rebuild one student's top-b from current + spare capacity.", "global welfare gain after exact rebuild", "current-student gain after rebuild", x, y + h, w0, w1, h);
  row(slide, ctx, "hybrid", "Try add/drop when seats are open; try swap when target is full.", "best move by ΔW_global", "best move by ΔU_student", x, y + 2 * h, w0, w1, h);

  rect(slide, ctx, 284, 548, 710, 46, S.dark);
  text(
    slide,
    ctx,
    "This matrix is the empirical lever: the same utility model can behave differently depending on the local operator and acceptance criterion.",
    314,
    561,
    650,
    18,
    { size: 13.5, color: S.white, face: S.titleFont, bold: true, align: "center" },
  );

  footer(slide, ctx, 8, "Source: README.md post-draft improvement modes");
  return slide;
}

function header(slide, ctx, label, x, y, w, color) {
  rect(slide, ctx, x, y, w, 42, color);
  text(slide, ctx, label, x + 18, y + 8, w - 36, 24, { size: 12, color: S.white, bold: true, align: "center" });
}

function row(slide, ctx, move, definition, globalText, personalText, x, y, w0, w1, h) {
  box(slide, ctx, x, y, w0, h, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, move, x + 18, y + 18, 150, 24, { size: 18, color: S.ink, face: S.titleFont, bold: true });
  text(slide, ctx, definition, x + 18, y + 48, 160, 28, { size: 9.5, color: S.muted });

  box(slide, ctx, x + w0, y, w1, h, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, globalText, x + w0 + 28, y + 29, w1 - 56, 28, { size: 13, color: S.teal, bold: true, align: "center" });

  box(slide, ctx, x + w0 + w1, y, w1, h, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, personalText, x + w0 + w1 + 28, y + 29, w1 - 56, 28, {
    size: 13,
    color: S.berry,
    bold: true,
    align: "center",
  });
}
