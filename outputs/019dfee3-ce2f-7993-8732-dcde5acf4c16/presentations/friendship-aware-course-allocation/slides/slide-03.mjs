import { S, arrowText, bg, box, footer, kicker, rect, text, title } from "./common.mjs";

export async function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Model inputs");
  title(slide, ctx, "Мы добавляем к индивидуальным ранжированиям направленный friendship graph.", {
    w: 920,
    h: 88,
    size: 34,
  });

  inputBox(slide, ctx, "Table 1", "StudentID, CourseID\nScore, Position", 74, 226, S.blue);
  inputBox(slide, ctx, "Table 2", "Student A -> Student B\nCourseID, Position, Score", 74, 348, S.berry);
  inputBox(slide, ctx, "Table 3", "StudentID\nLambdaFriend in [0,1]", 74, 470, S.teal);
  arrowText(slide, ctx, 320, 344, 112, S.teal);

  box(slide, ctx, 462, 206, 330, 356, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, "Feasible allocation", 488, 228, 250, 22, { size: 12, color: S.teal, bold: true });
  const students = ["S1", "S2", "S3", "S4"];
  const courses = ["C1", "C2", "C3"];
  students.forEach((s, i) => {
    text(slide, ctx, s, 500, 284 + i * 54, 38, 22, { size: 15, color: S.ink, bold: true });
  });
  courses.forEach((c, i) => {
    text(slide, ctx, c, 578 + i * 62, 258, 40, 20, { size: 12, color: S.muted, bold: true, align: "center" });
  });
  const marks = [
    [0, 0],
    [0, 2],
    [1, 1],
    [2, 0],
    [2, 1],
    [3, 2],
  ];
  for (let r = 0; r < students.length; r += 1) {
    for (let c = 0; c < courses.length; c += 1) {
      rect(slide, ctx, 574 + c * 62, 282 + r * 54, 34, 28, S.faint2);
    }
  }
  marks.forEach(([r, c]) => rect(slide, ctx, 574 + c * 62, 282 + r * 54, 34, 28, c === 1 ? S.gold : S.teal));
  text(slide, ctx, "capacity(c) and max bundle size b constrain every assignment.", 500, 512, 248, 28, {
    size: 11,
    color: S.muted,
  });

  arrowText(slide, ctx, 812, 344, 112, S.berry);
  box(slide, ctx, 954, 206, 252, 356, { fill: "#FFFCF4", stroke: S.faint });
  text(slide, ctx, "Directed social layer", 980, 228, 190, 22, { size: 12, color: S.berry, bold: true });
  socialEdge(slide, ctx, "S1", "S3", "C2", 988, 288, S.berry);
  socialEdge(slide, ctx, "S2", "S1", "C1", 988, 364, S.teal);
  socialEdge(slide, ctx, "S4", "S2", "C3", 988, 440, S.gold);
  text(slide, ctx, "Semantics: A wants to be in course c together with B.", 984, 518, 190, 28, {
    size: 10.5,
    color: S.muted,
  });

  footer(slide, ctx, 3, "Source: README.md input data format");
  return slide;
}

function inputBox(slide, ctx, label, body, x, y, color) {
  box(slide, ctx, x, y, 216, 80, { fill: "#FFFCF4", stroke: color });
  text(slide, ctx, label, x + 18, y + 14, 84, 20, { size: 12, color, bold: true });
  text(slide, ctx, body, x + 18, y + 38, 176, 32, { size: 11, color: S.ink });
}

function socialEdge(slide, ctx, a, b, course, x, y, color) {
  rect(slide, ctx, x, y, 46, 30, "#FFFFFF", { line: ctx.line(color, 1) });
  rect(slide, ctx, x + 132, y, 46, 30, "#FFFFFF", { line: ctx.line(color, 1) });
  text(slide, ctx, a, x, y + 6, 46, 16, { size: 12, color, bold: true, align: "center" });
  text(slide, ctx, b, x + 132, y + 6, 46, 16, { size: 12, color, bold: true, align: "center" });
  arrowText(slide, ctx, x + 54, y + 5, 70, color);
  text(slide, ctx, course, x + 70, y + 36, 40, 18, { size: 10, color: S.muted, align: "center", bold: true });
}
