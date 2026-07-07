const TOTAL = 12;

const C = {
  bg: "#F7F3EA",
  bg2: "#EFE7D9",
  ink: "#17212E",
  muted: "#56616F",
  faint: "#D7CDBE",
  faint2: "#E9DFCF",
  dark: "#17212E",
  dark2: "#223044",
  teal: "#0F766E",
  teal2: "#BFE3DC",
  berry: "#9F1239",
  berry2: "#E9B8C6",
  gold: "#B7791F",
  gold2: "#F1D49D",
  blue: "#355070",
  white: "#FFFFFF",
};

const DATA = {
  gains: [
    { label: "hybrid-global, post=5", value: 3.63, color: C.teal },
    { label: "swap-global, post=20", value: 2.21, color: C.blue },
    { label: "drop-add-global, post=20", value: 0.26, color: C.gold },
    { label: "hybrid-personal, post=20", value: -0.39, color: C.berry },
  ],
  tradeoffs: [
    { label: "Friend overlaps", before: "3.7145", after: "4.6965", delta: "+26.44%", color: C.teal, good: true },
    { label: "Average assigned rank", before: "2.186", after: "2.434", delta: "higher rank", color: C.berry, good: false },
    { label: "Top-3 share", before: "87.2%", after: "79.6%", delta: "-7.6 pp", color: C.berry, good: false },
    { label: "Normalized Gini", before: "0.05238", after: "0.05576", delta: "slight rise", color: C.gold, good: false },
  ],
};

export async function createSlide(n, presentation, ctx) {
  return [
    slide01, slide02, slide03, slide04, slide05, slide06,
    slide07, slide08, slide09, slide10, slide11, slide12,
  ][n - 1](presentation, ctx);
}

function bg(slide, ctx, dark = false) {
  rect(slide, ctx, 0, 0, ctx.W, ctx.H, dark ? C.dark : C.bg);
}

function rect(slide, ctx, x, y, w, h, fill, opts = {}) {
  return ctx.addShape(slide, {
    left: x, top: y, width: w, height: h,
    geometry: opts.geometry ?? "rect",
    fill,
    line: opts.line ?? ctx.line(opts.stroke ?? "#00000000", opts.weight ?? 0),
  });
}

function line(slide, ctx, x, y, w, color = C.faint, weight = 1) {
  rect(slide, ctx, x, y, w, weight, color);
}

function vline(slide, ctx, x, y, h, color = C.faint, weight = 1) {
  rect(slide, ctx, x, y, weight, h, color);
}

function text(slide, ctx, value, x, y, w, h, opts = {}) {
  return ctx.addText(slide, {
    text: String(value ?? ""),
    left: x, top: y, width: w, height: h,
    fontSize: opts.size ?? 16,
    color: opts.color ?? (opts.dark ? C.white : C.ink),
    bold: Boolean(opts.bold),
    typeface: opts.face ?? (opts.mono ? "Aptos Mono" : "Arial"),
    align: opts.align ?? "left",
    valign: opts.valign ?? "top",
    fill: opts.fill ?? "#00000000",
    line: opts.line ?? ctx.line("#00000000", 0),
    insets: opts.insets ?? { left: 0, right: 0, top: 0, bottom: 0 },
  });
}

function kicker(slide, ctx, label, dark = false) {
  rect(slide, ctx, 58, 48, 7, 22, dark ? C.gold2 : C.teal);
  text(slide, ctx, label, 78, 45, 560, 28, {
    size: 10, color: dark ? "#C7D7EA" : C.muted, bold: true, valign: "middle",
  });
}

function title(slide, ctx, value, opts = {}) {
  text(slide, ctx, value, opts.x ?? 58, opts.y ?? 86, opts.w ?? 960, opts.h ?? 92, {
    size: opts.size ?? 35, color: opts.color ?? (opts.dark ? C.white : C.ink),
    bold: true, dark: opts.dark,
  });
}

function sub(slide, ctx, value, x, y, w, h, opts = {}) {
  text(slide, ctx, value, x, y, w, h, {
    size: opts.size ?? 14, color: opts.color ?? (opts.dark ? "#C7D7EA" : C.muted), dark: opts.dark,
  });
}

function footer(slide, ctx, n, source, dark = false) {
  line(slide, ctx, 58, 668, 1164, dark ? "#41516A" : C.faint, 1);
  text(slide, ctx, source, 58, 682, 900, 18, { size: 8.5, color: dark ? "#9FB0C5" : "#7A6E60", dark });
  text(slide, ctx, `${n}/${TOTAL}`, 1162, 682, 60, 18, { size: 9, color: dark ? "#C7D7EA" : C.muted, align: "right", dark });
}

function card(slide, ctx, x, y, w, h, opts = {}) {
  rect(slide, ctx, x, y, w, h, opts.fill ?? "#FFFCF4", { stroke: opts.stroke ?? C.faint, weight: 1 });
}

function labelCard(slide, ctx, label, body, x, y, w, h, opts = {}) {
  card(slide, ctx, x, y, w, h, opts);
  text(slide, ctx, label, x + 18, y + 16, w - 36, 22, { size: opts.labelSize ?? 12, color: opts.labelColor ?? C.teal, bold: true });
  text(slide, ctx, body, x + 18, y + 46, w - 36, h - 62, { size: opts.bodySize ?? 13.4, color: opts.bodyColor ?? C.ink, dark: opts.dark });
}

function pill(slide, ctx, value, x, y, w, fill, color = C.ink) {
  rect(slide, ctx, x, y, w, 28, fill);
  text(slide, ctx, value, x + 12, y + 5, w - 24, 18, { size: 10, color, bold: true, align: "center" });
}

function metric(slide, ctx, value, label, note, x, y, opts = {}) {
  vline(slide, ctx, x, y - 2, 58, opts.color ?? C.teal, 3);
  text(slide, ctx, value, x + 16, y, 150, 34, { size: opts.valueSize ?? 28, color: opts.valueColor ?? C.ink, bold: true });
  text(slide, ctx, label, x + 16, y + 36, 150, 18, { size: 10, color: opts.labelColor ?? C.muted, bold: true });
  text(slide, ctx, note, x + 16, y + 54, 170, 26, { size: 8.5, color: opts.noteColor ?? C.muted });
}

function slide01(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Deliverable 2 | Research Proposal Project");
  title(slide, ctx, "Friendship-Aware Course Allocation: An Empirical Research Proposal", { x: 430, y: 108, w: 770, h: 118, size: 41 });
  sub(slide, ctx, "An HBS-style snake draft mechanism that incorporates directed friendship preferences, reactive social utility, and post-allocation local search.", 430, 250, 740, 52, { size: 16 });
  rect(slide, ctx, 70, 96, 300, 422, C.dark);
  text(slide, ctx, "Research core", 104, 126, 230, 24, { size: 12, color: "#C7D7EA", bold: true, dark: true });
  text(slide, ctx, "When students\ncare who they\nstudy with", 104, 166, 230, 126, { size: 34, color: C.white, bold: true, dark: true });
  text(slide, ctx, "The project tests how friendship relations inside an allocation mechanism change welfare, social satisfaction, ranking outcomes, and fairness.", 104, 324, 226, 86, { size: 14, color: "#D9E2EF", dark: true });
  pill(slide, ctx, "computational empirical", 116, 438, 202, C.gold2, C.dark);
  metric(slide, ctx, "01", "Mechanism", "deterministic snake draft", 468, 390, { color: C.teal });
  metric(slide, ctx, "02", "Social variable", "student-level LambdaFriend", 690, 390, { color: C.berry });
  metric(slide, ctx, "03", "Evaluation", "welfare, fairness, overlaps", 912, 390, { color: C.gold });
  card(slide, ctx, 434, 552, 735, 72, { fill: "#FFFCF4" });
  text(slide, ctx, "Research claim", 462, 570, 110, 18, { size: 10, color: C.teal, bold: true });
  text(slide, ctx, "Adding social preferences may increase system welfare and social satisfaction, but it can also create costs in ranking satisfaction and fairness.", 590, 568, 530, 42, { size: 15, color: C.ink, bold: true });
  footer(slide, ctx, 1, "Sources: README.md; project_presentation_materials.txt");
  return slide;
}

function slide02(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Introduction and theoretical background");
  title(slide, ctx, "The gap: course allocation mechanisms often assume independent student preferences.");
  sub(slide, ctx, "In practice, a student may value a course not only for content, instructor, or schedule, but also for the peers who will be there.", 58, 198, 760, 40);
  labelCard(slide, ctx, "Research phenomenon", "Course allocation is a one-sided assignment problem: students receive bundles of indivisible seats under course-capacity constraints.", 118, 262, 310, 192, { labelColor: C.blue });
  labelCard(slide, ctx, "Knowledge gap", "The literature emphasizes fairness, efficiency, strategy, and capacity. Friendship relations rarely enter the allocation model itself.", 486, 262, 310, 192, { labelColor: C.berry });
  labelCard(slide, ctx, "Research proposal", "Add a directed, course-specific social utility layer and evaluate its effect on welfare, friend overlaps, rank satisfaction, and inequality.", 852, 262, 310, 192, { labelColor: C.teal });
  line(slide, ctx, 154, 515, 982, C.faint, 1);
  text(slide, ctx, "Gap statement", 154, 542, 120, 20, { size: 11, color: C.teal, bold: true });
  text(slide, ctx, "The study asks what happens when preferences are socially interdependent and depend on other students' allocation outcomes.", 292, 538, 770, 44, { size: 17, bold: true });
  footer(slide, ctx, 2, "Sources: local project materials; Budish & Cantillon 2012; Budish 2011");
  return slide;
}

function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Focused literature review");
  title(slide, ctx, "The literature explains fair and efficient allocation, but not the social coupling between student choices.", { size: 33 });
  const cols = [
    ["Course allocation", "Multi-unit assignment, capacity, course bundles, HBS draft.\nAnchor: Budish & Cantillon."],
    ["Allocation mechanisms", "RSD, draft, A-CEEI, fair division, strategyproofness.\nAnchors: Budish; Abdulkadiroglu & Sonmez."],
    ["Social preferences", "Utility is not purely individual: fairness, reciprocity, social welfare.\nAnchors: Fehr & Schmidt; Charness & Rabin."],
    ["Proposed gap", "No operational layer for directed, course-specific, reactive friendship preferences inside course choice."],
  ];
  const xs = [86, 362, 638, 914];
  cols.forEach((col, i) => {
    card(slide, ctx, xs[i], 236, 230, 270, { fill: i === 3 ? C.dark : "#FFFCF4", stroke: i === 3 ? C.dark : C.faint });
    text(slide, ctx, col[0], xs[i] + 18, 258, 194, 30, { size: 15, color: i === 3 ? C.gold2 : [C.blue, C.teal, C.gold, C.berry][i], bold: true, dark: i === 3 });
    text(slide, ctx, col[1], xs[i] + 18, 306, 194, 158, { size: 12.3, color: i === 3 ? "#D9E2EF" : C.ink, dark: i === 3 });
  });
  text(slide, ctx, "Integrated theoretical frame", 154, 560, 190, 20, { size: 11, color: C.teal, bold: true });
  text(slide, ctx, "Mechanism design provides the allocation language; social-preference theory explains why students may value others' outcomes.", 368, 556, 690, 42, { size: 15.5, bold: true });
  footer(slide, ctx, 3, "Literature anchors: course allocation, fair division, school choice, social preferences");
  return slide;
}

function slide04(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Research questions and hypotheses");
  title(slide, ctx, "The hypotheses focus on welfare, social mediation, individual cost, and market-condition moderation.");
  const rows = [
    ["RQ1", "How does incorporating friendship preferences affect total allocation utility?", "H1", "Social utility will increase total utility relative to a no-post draft, especially when social-network density is sufficient."],
    ["RQ2", "Do friend overlaps mediate the mechanism's effect on welfare?", "H2", "The effect of hybrid-global on welfare will be partially mediated by increased same-course friend overlaps."],
    ["RQ3", "Does the social gain trade off against rank satisfaction and fairness?", "H3", "Higher social utility will be associated with worse average rank and a moderate increase in inequality."],
    ["RQ4", "When is the mechanism more or less effective?", "H4", "The mechanism effect will be moderated by LambdaFriend, friendship density, and capacity pressure."],
  ];
  rows.forEach((r, i) => {
    const y = 184 + i * 96;
    rect(slide, ctx, 138, y, 64, 28, C.blue);
    text(slide, ctx, r[0], 138, y + 5, 64, 18, { size: 10, color: C.white, bold: true, align: "center", dark: true });
    text(slide, ctx, r[1], 222, y, 310, 58, { size: 12.7, color: C.ink, bold: true });
    rect(slide, ctx, 582, y, 64, 28, C.teal);
    text(slide, ctx, r[2], 582, y + 5, 64, 18, { size: 10, color: C.white, bold: true, align: "center", dark: true });
    text(slide, ctx, r[3], 666, y, 420, 62, { size: 12.2, color: C.ink });
    line(slide, ctx, 132, y + 76, 982, C.faint, 1);
  });
  footer(slide, ctx, 4, "Research questions and hypotheses synthesized from model + preliminary computational evidence");
  return slide;
}

function slide05(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Research model");
  title(slide, ctx, "The model links individual preferences, friendship preferences, and multi-dimensional outcomes.");
  labelCard(slide, ctx, "Input variables", "Individual course rankings\nDirected course-specific friendships\nStudent-level LambdaFriend", 128, 228, 286, 132, { labelColor: C.blue, bodySize: 13 });
  labelCard(slide, ctx, "Mechanism", "HBS-style snake draft\n+ reactive friend bonus\n+ deterministic tie-breaking", 496, 228, 286, 132, { labelColor: C.teal, bodySize: 13 });
  labelCard(slide, ctx, "Post-allocation improvement", "swap / drop-add / hybrid\nobjective scope:\nglobal or personal", 864, 228, 286, 132, { labelColor: C.gold, bodySize: 13 });
  text(slide, ctx, "→", 432, 266, 44, 44, { size: 28, color: C.muted, align: "center" });
  text(slide, ctx, "→", 800, 266, 44, 44, { size: 28, color: C.muted, align: "center" });
  card(slide, ctx, 402, 420, 480, 84, { fill: C.dark, stroke: C.dark });
  text(slide, ctx, "Mediation: realized friend overlaps", 432, 442, 260, 22, { size: 13, color: C.gold2, bold: true, dark: true });
  text(slide, ctx, "Does welfare improvement operate through more friends sharing the same course?", 432, 466, 398, 22, { size: 12.5, color: "#D9E2EF", dark: true });
  labelCard(slide, ctx, "Outcomes", "total utility\nsocial utility\naverage rank / Top-3\nGini, Jain, Theil, Atkinson", 140, 528, 316, 112, { labelColor: C.teal, bodySize: 11.5 });
  labelCard(slide, ctx, "Moderators", "friendship-network density\ncapacity pressure\nLambdaFriend values", 815, 528, 316, 112, { labelColor: C.berry, bodySize: 11.5 });
  footer(slide, ctx, 5, "Sources: README utility model; local experiment design");
  return slide;
}

function slide06(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Research method");
  title(slide, ctx, "The study is a comparative computational experiment with repeated seeds and controlled parameters.");
  const headers = ["Factor", "Levels / manipulation", "Purpose"];
  const rows = [
    ["Improvement mode", "none, swap, drop-add, hybrid", "Test whether local search improves the base draft"],
    ["Objective scope", "global vs. personal", "Separate system welfare from individual gains"],
    ["Social weight", "LambdaFriend: 0 to 1", "Test the strength of social preference"],
    ["Market scenario", "courses, capacities, friendship density", "Assess sensitivity and external validity"],
  ];
  drawTable(slide, ctx, 116, 214, [238, 388, 410], 58, headers, rows);
  card(slide, ctx, 146, 564, 988, 68, { fill: "#FFFCF4" });
  text(slide, ctx, "Unit of analysis", 174, 582, 116, 18, { size: 10, color: C.teal, bold: true });
  text(slide, ctx, "One algorithm run is defined by scenario, seed, improvement mode, post-iteration count, and LambdaFriend; outcomes are computed at the run level and compared across conditions.", 312, 580, 780, 40, { size: 13.5, bold: true });
  footer(slide, ctx, 6, "Sources: generate/generate_tables.py; HBS/hbs_experiments.py; results/experiments");
  return slide;
}

function slide07(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Measurement, reliability, and validity");
  title(slide, ctx, "Robust measurement separates allocation quality, social satisfaction, rank satisfaction, and fairness.");
  const domains = [
    ["Welfare", "total_utility, avg_utility_per_student, total_base_utility", "Decomposes baseline value and social value"],
    ["Social satisfaction", "avg_friend_overlaps_per_student, share_any_overlap", "Construct validity: realized friendship preferences"],
    ["Individual satisfaction", "avg_position, median_position, share_top1, share_top3", "Captures the individual cost of social utility"],
    ["Fairness / inequality", "Gini, Jain, Theil, Atkinson, percentiles", "Sensitive to distribution, not just the mean"],
  ];
  domains.forEach((d, i) => {
    const x = i < 2 ? 116 : 672;
    const y = i % 2 === 0 ? 226 : 416;
    card(slide, ctx, x, y, 492, 142, { fill: "#FFFCF4" });
    text(slide, ctx, d[0], x + 24, y + 20, 430, 24, { size: 15, color: [C.teal, C.blue, C.gold, C.berry][i], bold: true });
    text(slide, ctx, d[1], x + 24, y + 54, 430, 34, { size: 12.5, mono: true, color: C.ink });
    text(slide, ctx, d[2], x + 24, y + 100, 430, 24, { size: 12.5, color: C.muted });
  });
  text(slide, ctx, "Reliability", 154, 592, 90, 18, { size: 10, color: C.teal, bold: true });
  text(slide, ctx, "Fixed seed, deterministic tie-breaking, and 44 automated tests that passed in the local project materials.", 258, 588, 760, 28, { size: 14.5, bold: true });
  footer(slide, ctx, 7, "Sources: README metrics; tests/run_all_tests.py; project materials");
  return slide;
}

function slide08(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Data analysis plan");
  title(slide, ctx, "The analysis combines condition comparisons, regression models, mediation/moderation, and robustness checks.");
  const steps = [
    ["01", "Describe and validate", "Baseline statistics, distributions, capacity and feasibility checks"],
    ["02", "Test hypotheses", "Compare none vs. improvement modes, and global vs. personal objectives"],
    ["03", "Model effects", "Regression / mixed effects with seed and scenario as controls"],
    ["04", "Check robustness", "Sensitivity to LambdaFriend, friendship density, capacity pressure, and iterations"],
  ];
  steps.forEach((s, i) => {
    const y = 204 + i * 82;
    rect(slide, ctx, 238, y, 54, 54, [C.blue, C.teal, C.gold, C.berry][i]);
    text(slide, ctx, s[0], 238, y + 14, 54, 22, { size: 15, color: C.white, bold: true, align: "center", dark: true });
    text(slide, ctx, s[1], 316, y + 5, 152, 22, { size: 14, color: C.ink, bold: true });
    text(slide, ctx, s[2], 504, y + 5, 520, 40, { size: 13, color: C.muted });
    if (i < steps.length - 1) vline(slide, ctx, 264, y + 58, 24, C.faint, 2);
  });
  card(slide, ctx, 1050, 214, 166, 272, { fill: C.dark, stroke: C.dark });
  text(slide, ctx, "Methodological principle", 1074, 244, 118, 34, { size: 10, color: C.gold2, bold: true, dark: true });
  text(slide, ctx, "One mean is not enough", 1074, 292, 118, 58, { size: 22, color: C.white, bold: true, dark: true });
  text(slide, ctx, "The study must report the welfare-social-rank-fairness trade-off frontier.", 1074, 382, 118, 72, { size: 12, color: "#D9E2EF", dark: true });
  footer(slide, ctx, 8, "Analysis plan: repeated computational experiment; multi-metric outcome framework");
  return slide;
}

function slide09(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Preliminary evidence");
  title(slide, ctx, "In the 200x8 scenario, hybrid-global captures most welfare improvement within five iterations.", { size: 34 });
  text(slide, ctx, "Mean total-utility change vs. no-post baseline", 520, 208, 444, 20, { size: 12, color: C.muted, bold: true });
  DATA.gains.forEach((item, i) => gainBar(slide, ctx, item, 150, 262 + i * 66));
  card(slide, ctx, 872, 512, 246, 140, { fill: "#FFFCF4" });
  text(slide, ctx, "Baseline", 902, 528, 86, 14, { size: 9, color: C.muted, bold: true });
  text(slide, ctx, "371.310", 902, 546, 156, 30, { size: 24, color: C.ink, bold: true });
  text(slide, ctx, "hybrid-global post=5", 902, 584, 144, 14, { size: 8.5, color: C.teal, bold: true });
  text(slide, ctx, "384.805", 902, 604, 202, 30, { size: 23, color: C.teal, bold: true });
  text(slide, ctx, "Careful interpretation: these are preliminary computational results from a synthetic artifact set; they show direction and feasibility, not final evidence on real students.", 142, 574, 600, 44, { size: 13.5, color: C.muted });
  footer(slide, ctx, 9, "Source: results/experiments/A_200x8_mode_post_agg_partial.csv; seeds 11-20");
  return slide;
}

function slide10(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Cost and value");
  title(slide, ctx, "The social gain creates a measurable trade-off with rank satisfaction and inequality.");
  DATA.tradeoffs.forEach((d, i) => {
    const x = i < 2 ? 118 : 666;
    const y = i % 2 === 0 ? 226 : 404;
    tradeCard(slide, ctx, d, x, y);
  });
  card(slide, ctx, 414, 570, 452, 62, { fill: C.dark, stroke: C.dark });
  text(slide, ctx, "Hypothesis implication", 442, 586, 144, 18, { size: 10, color: C.gold2, bold: true, dark: true });
  text(slide, ctx, "H2 is directionally supported; H3 defines the cost that the full study must quantify.", 610, 584, 230, 34, { size: 13, color: C.white, dark: true });
  footer(slide, ctx, 10, "Source: local A_200x8 preliminary metrics from project_presentation_materials.txt");
  return slide;
}

function slide11(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "Expected research contribution");
  title(slide, ctx, "The contribution is a measurable model of social preferences inside an allocation mechanism.");
  labelCard(slide, ctx, "Theoretical contribution", "Extends course allocation from independent preferences to a socially coupled assignment model where one student's value can depend on others' allocations.", 130, 236, 300, 224, { labelColor: C.teal, bodySize: 14 });
  labelCard(slide, ctx, "Methodological contribution", "Provides an experimental framework that separates mechanism, objective scope, social weight, welfare metrics, and fairness metrics.", 490, 236, 300, 224, { labelColor: C.blue, bodySize: 14 });
  labelCard(slide, ctx, "Future research implications", "Enables studies using real preference data, survey-based friendship measures, timetable constraints, privacy, and strategic reporting.", 850, 236, 300, 224, { labelColor: C.gold, bodySize: 14 });
  text(slide, ctx, "Not only an algorithmic improvement", 154, 548, 242, 24, { size: 13, color: C.berry, bold: true });
  text(slide, ctx, "The proposal offers an empirical language for measuring the cost and value of social ties in institutional allocation systems.", 420, 544, 690, 44, { size: 16, bold: true });
  footer(slide, ctx, 11, "Contribution synthesized from proposal structure and local prototype");
  return slide;
}

function slide12(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx, true);
  kicker(slide, ctx, "Robustness and limitations", true);
  title(slide, ctx, "The next step is moving from feasibility evidence to a full research design.", { dark: true, size: 34 });
  const items = [
    ["Limitation", "Current data are synthetic, so they do not establish external validity for a real student population."],
    ["Robustness", "The experiment should expand scenarios: friendship density, capacities, Lambda values, seeds, and iteration counts."],
    ["Validity", "Future work should combine real preference data or surveys with tests of whether reported friendships behave like the model."],
    ["Ethics and privacy", "Friendship preferences are sensitive data; future research requires anonymization, consent, and careful data governance."],
  ];
  items.forEach((item, i) => {
    const x = i < 2 ? 118 : 666;
    const y = i % 2 === 0 ? 220 : 404;
    rect(slide, ctx, x, y, 486, 132, "#223044", { stroke: "#41516A", weight: 1 });
    text(slide, ctx, item[0], x + 26, y + 22, 420, 22, { size: 14, color: i === 0 ? C.berry2 : C.gold2, bold: true, dark: true });
    text(slide, ctx, item[1], x + 26, y + 56, 420, 52, { size: 13, color: "#D9E2EF", dark: true });
  });
  text(slide, ctx, "Closing", 154, 596, 64, 18, { size: 10, color: C.gold2, bold: true, dark: true });
  text(slide, ctx, "The proposal centers on a measurable trade-off: more social satisfaction and system welfare, with possible costs in rank satisfaction and fairness.", 236, 590, 760, 44, { size: 15.5, color: C.white, bold: true, dark: true });
  footer(slide, ctx, 12, "Final slide: limitations, robustness plan, and next research steps", true);
  return slide;
}

function drawTable(slide, ctx, x, y, widths, rowH, headers, rows) {
  const totalW = widths.reduce((a, b) => a + b, 0);
  rect(slide, ctx, x, y, totalW, 42, C.dark, { stroke: C.dark });
  let cursor = x;
  headers.forEach((h, i) => {
    text(slide, ctx, h, cursor + 12, y + 12, widths[i] - 24, 18, { size: 11, color: C.white, bold: true, dark: true });
    cursor += widths[i];
  });
  rows.forEach((row, r) => {
    const yy = y + 42 + r * rowH;
    rect(slide, ctx, x, yy, totalW, rowH, r % 2 === 0 ? "#FFFCF4" : C.bg2, { stroke: C.faint, weight: 1 });
    let cx = x;
    row.forEach((cell, i) => {
      text(slide, ctx, cell, cx + 12, yy + 12, widths[i] - 24, rowH - 28, { size: i === 0 ? 12.5 : 12, color: i === 0 ? C.teal : C.ink, bold: i === 0 });
      cx += widths[i];
    });
  });
}

function gainBar(slide, ctx, item, x, y) {
  const labelW = 294;
  const trackW = 370;
  const zero = x + labelW + 58;
  const scale = 76;
  text(slide, ctx, item.label, x + labelW + trackW - 130, y - 8, 424, 18, { size: 12, color: C.ink, bold: true, align: "right" });
  rect(slide, ctx, x + labelW, y + 28, trackW, 12, C.faint2);
  vline(slide, ctx, zero, y + 20, 30, C.muted, 1);
  if (item.value >= 0) rect(slide, ctx, zero, y + 24, Math.max(3, item.value * scale), 20, item.color);
  else rect(slide, ctx, zero + item.value * scale, y + 24, Math.max(3, Math.abs(item.value) * scale), 20, item.color);
  text(slide, ctx, `${item.value > 0 ? "+" : ""}${item.value.toFixed(2)}%`, x + labelW + trackW + 18, y + 24, 88, 24, { size: 15, color: item.color, bold: true });
}

function tradeCard(slide, ctx, item, x, y) {
  card(slide, ctx, x, y, 496, 154, { fill: "#FFFCF4" });
  text(slide, ctx, item.label, x + 24, y + 18, 440, 22, { size: 15, color: item.color, bold: true });
  text(slide, ctx, "before", x + 78, y + 58, 50, 16, { size: 9.5, color: C.muted, bold: true });
  text(slide, ctx, item.before, x + 78, y + 78, 132, 30, { size: 24, color: C.ink, bold: true });
  text(slide, ctx, "after", x + 260, y + 58, 50, 16, { size: 9.5, color: C.muted, bold: true });
  text(slide, ctx, item.after, x + 260, y + 78, 140, 30, { size: 24, color: item.color, bold: true });
  text(slide, ctx, "→", x + 220, y + 76, 34, 28, { size: 20, color: C.muted, align: "center" });
  pill(slide, ctx, item.delta, x + 260, y + 112, 160, item.good ? C.teal2 : C.berry2, item.good ? C.teal : C.berry);
}
