import { S, arrowText, bg, box, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide05(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Reactive bonus");
  title(slide, ctx, "Friend bonus is reactive, so each pick has a well-defined state.", {
    w: 900,
    h: 86,
    size: 34,
  });

  stage(slide, ctx, "t = 1", "S1 picks C1", "No previous friend allocation can contribute to S1's bonus.", 90, 238, S.blue);
  arrowText(slide, ctx, 356, 310, 110, S.teal);
  stage(
    slide,
    ctx,
    "t = 2",
    "S2 evaluates C1",
    "If S2 lists S1 as a friend for C1, then S1's existing seat creates social utility.",
    500,
    238,
    S.teal,
  );
  arrowText(slide, ctx, 766, 310, 110, S.berry);
  stage(slide, ctx, "t = 3", "S3 evaluates C1", "Only friends already in C1 count; future choices are not anticipated.", 910, 238, S.berry);

  box(slide, ctx, 156, 504, 968, 58, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, "Mathematical consequence", 184, 520, 178, 20, { size: 11, color: S.teal, bold: true });
  text(
    slide,
    ctx,
    "The indicator 1[c ∈ A_f] makes the utility computable at the moment of each pick and avoids simultaneous circular dependence among students.",
    378,
    518,
    704,
    24,
    { size: 14, color: S.ink, face: S.titleFont, bold: true },
  );

  footer(slide, ctx, 5, "Source: README.md reactive friend bonus");
  return slide;
}

function stage(slide, ctx, t, claim, body, x, y, color) {
  box(slide, ctx, x, y, 236, 180, { fill: "#FFFCF4", stroke: color });
  rect(slide, ctx, x + 22, y + 24, 54, 30, color);
  text(slide, ctx, t, x + 22, y + 30, 54, 16, { size: 11, color: S.white, bold: true, align: "center" });
  text(slide, ctx, claim, x + 92, y + 24, 112, 36, { size: 17, color: S.ink, face: S.titleFont, bold: true });
  text(slide, ctx, body, x + 28, y + 86, 180, 56, { size: 12, color: S.muted });
  rect(slide, ctx, x + 32, y + 142, 40, 20, S.faint2);
  rect(slide, ctx, x + 84, y + 142, 40, 20, color);
  rect(slide, ctx, x + 136, y + 142, 40, 20, S.faint2);
  text(slide, ctx, "course seats", x + 38, y + 164, 132, 12, { size: 7.5, color: S.muted, align: "center" });
}
