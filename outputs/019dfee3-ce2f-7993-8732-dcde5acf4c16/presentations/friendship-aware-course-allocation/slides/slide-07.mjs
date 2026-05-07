import { S, arrowText, bg, box, footer, kicker, stepNode, text, title } from "./common.mjs";

export async function slide07(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Post-allocation stage");
  title(slide, ctx, "Post-allocation search treats the draft as a feasible starting point, not the endpoint.", {
    w: 960,
    h: 90,
    size: 33,
  });

  const y = 238;
  stepNode(slide, ctx, 1, "Initial draft", "A complete feasible allocation from the snake draft.", 76, y, 224, 130, {
    numColor: S.blue,
  });
  arrowText(slide, ctx, 310, y + 54, 64, S.teal);
  stepNode(slide, ctx, 2, "Candidate move", "Swap, drop-add, or hybrid move proposed by local search.", 386, y, 250, 130, {
    numColor: S.teal,
  });
  arrowText(slide, ctx, 648, y + 54, 64, S.berry);
  stepNode(slide, ctx, 3, "Feasibility", "Capacity and max-bundle constraints must remain satisfied.", 724, y, 224, 130, {
    numColor: S.gold,
  });
  arrowText(slide, ctx, 960, y + 54, 64, S.gold);
  stepNode(slide, ctx, 4, "Accept / reject", "Move is accepted only if the selected objective strictly improves.", 1036, y, 170, 130, {
    numColor: S.berry,
    labelSize: 13,
    bodySize: 9.5,
  });

  box(slide, ctx, 132, 452, 1008, 82, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, "Why this stage matters", 164, 472, 180, 20, { size: 12, color: S.teal, bold: true });
  text(
    slide,
    ctx,
    "The draft is fast and deterministic, but early choices create path dependence. Local search asks whether feasible exchanges can improve welfare or individual utility after more social information is revealed.",
    364,
    470,
    724,
    36,
    { size: 14, color: S.ink, face: S.titleFont, bold: true },
  );

  footer(slide, ctx, 7, "Source: README.md post-draft improvement");
  return slide;
}
