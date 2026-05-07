import { S, bg, box, footer, formula, kicker, rect, text, title } from "./common.mjs";

export async function slide04(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Utility model");
  title(slide, ctx, "Utility decomposes into course value and a normalized social bonus.", {
    w: 900,
    h: 86,
    size: 34,
  });

  formula(slide, ctx, "Base(s,c) = posU(Position_A(s,c), |C|)", 72, 214, 470, 76, { size: 22 });
  formula(
    slide,
    ctx,
    "FriendBonus(s,c) = Σ_f 1[c ∈ A_f] · Pref(s,f,c)",
    72,
    318,
    470,
    86,
    { size: 21, stroke: S.berry },
  );
  formula(
    slide,
    ctx,
    "U(s,c) = (1 - λ_s) · Base(s,c) + λ_s · FriendBonusNorm(s,c)",
    72,
    432,
    470,
    96,
    { size: 20, stroke: S.teal },
  );

  box(slide, ctx, 620, 214, 520, 216, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, "Interpretation of λ_s", 650, 238, 240, 24, { size: 13, color: S.teal, bold: true });
  rect(slide, ctx, 660, 310, 380, 12, S.faint2);
  rect(slide, ctx, 660, 310, 190, 12, S.teal);
  rect(slide, ctx, 650, 298, 32, 36, S.blue);
  rect(slide, ctx, 835, 298, 32, 36, S.teal);
  rect(slide, ctx, 1024, 298, 32, 36, S.berry);
  text(slide, ctx, "λ = 0", 624, 348, 86, 20, { size: 12, color: S.blue, bold: true, align: "center" });
  text(slide, ctx, "λ = 0.5", 806, 348, 90, 20, { size: 12, color: S.teal, bold: true, align: "center" });
  text(slide, ctx, "λ = 1", 992, 348, 86, 20, { size: 12, color: S.berry, bold: true, align: "center" });
  text(slide, ctx, "pure individual\npreference", 618, 374, 96, 38, { size: 10.5, color: S.muted, align: "center" });
  text(slide, ctx, "convex\ntrade-off", 806, 374, 90, 38, { size: 10.5, color: S.muted, align: "center" });
  text(slide, ctx, "pure social\nterm", 988, 374, 96, 38, { size: 10.5, color: S.muted, align: "center" });

  box(slide, ctx, 620, 462, 520, 82, { stroke: S.faint });
  text(slide, ctx, "Why normalize?", 650, 480, 150, 20, { size: 12, color: S.berry, bold: true });
  text(
    slide,
    ctx,
    "Students can have different numbers and intensities of friend preferences; normalization keeps the social term comparable across students.",
    812,
    480,
    286,
    42,
    { size: 11.5, color: S.muted },
  );

  footer(slide, ctx, 4, "Source: README.md mathematical model");
  return slide;
}
