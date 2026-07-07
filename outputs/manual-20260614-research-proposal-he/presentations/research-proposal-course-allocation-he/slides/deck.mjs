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
  blue2: "#CAD8EA",
  white: "#FFFFFF",
};

const DATA = {
  baselineU: 371.310,
  hybridU: 384.805,
  gains: [
    { label: "hybrid-global, post=5", value: 3.63, color: C.teal },
    { label: "swap-global, post=20", value: 2.21, color: C.blue },
    { label: "drop-add-global, post=20", value: 0.26, color: C.gold },
    { label: "hybrid-personal, post=20", value: -0.39, color: C.berry },
  ],
  tradeoffs: [
    { label: "חפיפות חברים", before: "3.7145", after: "4.6965", delta: "+26.44%", color: C.teal, good: true },
    { label: "דירוג ממוצע", before: "2.186", after: "2.434", delta: "גבוה יותר", color: C.berry, good: false },
    { label: "שיעור Top-3", before: "87.2%", after: "79.6%", delta: "-7.6 נק'", color: C.berry, good: false },
    { label: "Gini מנורמל", before: "0.05238", after: "0.05576", delta: "עלייה קלה", color: C.gold, good: false },
  ],
};

export async function createSlide(n, presentation, ctx) {
  const map = {
    1: slide01,
    2: slide02,
    3: slide03,
    4: slide04,
    5: slide05,
    6: slide06,
    7: slide07,
    8: slide08,
    9: slide09,
    10: slide10,
    11: slide11,
    12: slide12,
  };
  return map[n](presentation, ctx);
}

function bg(slide, ctx, dark = false) {
  rect(slide, ctx, 0, 0, ctx.W, ctx.H, dark ? C.dark : C.bg);
}

function rect(slide, ctx, x, y, w, h, fill, opts = {}) {
  return ctx.addShape(slide, {
    left: x,
    top: y,
    width: w,
    height: h,
    geometry: opts.geometry ?? "rect",
    fill,
    line: opts.line ?? ctx.line(opts.stroke ?? "#00000000", opts.weight ?? 0),
    name: opts.name,
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
    left: x,
    top: y,
    width: w,
    height: h,
    fontSize: opts.size ?? 16,
    color: opts.color ?? (opts.dark ? C.white : C.ink),
    bold: Boolean(opts.bold),
    typeface: opts.face ?? (opts.mono ? "Aptos Mono" : "Arial"),
    align: opts.align ?? "right",
    valign: opts.valign ?? "top",
    fill: opts.fill ?? "#00000000",
    line: opts.line ?? ctx.line("#00000000", 0),
    insets: opts.insets ?? { left: 0, right: 0, top: 0, bottom: 0 },
    name: opts.name,
  });
}

function kicker(slide, ctx, label, dark = false) {
  rect(slide, ctx, 1205, 48, 7, 22, dark ? C.gold2 : C.teal);
  text(slide, ctx, label, 652, 45, 536, 28, {
    size: 10,
    color: dark ? "#C7D7EA" : C.muted,
    bold: true,
    valign: "middle",
  });
}

function title(slide, ctx, value, opts = {}) {
  text(slide, ctx, value, opts.x ?? 300, opts.y ?? 84, opts.w ?? 912, opts.h ?? 86, {
    size: opts.size ?? 35,
    color: opts.color ?? (opts.dark ? C.white : C.ink),
    bold: true,
    face: "Arial",
    dark: opts.dark,
  });
}

function sub(slide, ctx, value, x, y, w, h, opts = {}) {
  text(slide, ctx, value, x, y, w, h, {
    size: opts.size ?? 14,
    color: opts.color ?? (opts.dark ? "#C7D7EA" : C.muted),
    dark: opts.dark,
  });
}

function footer(slide, ctx, n, source, dark = false) {
  line(slide, ctx, 58, 668, 1164, dark ? "#41516A" : C.faint, 1);
  text(slide, ctx, source, 58, 682, 900, 18, {
    size: 8.5,
    color: dark ? "#9FB0C5" : "#7A6E60",
    align: "left",
    dark,
  });
  text(slide, ctx, `${n}/${TOTAL}`, 1162, 682, 60, 18, {
    size: 9,
    color: dark ? "#C7D7EA" : C.muted,
    align: "right",
    dark,
  });
}

function card(slide, ctx, x, y, w, h, opts = {}) {
  rect(slide, ctx, x, y, w, h, opts.fill ?? "#FFFCF4", {
    stroke: opts.stroke ?? C.faint,
    weight: opts.weight ?? 1,
  });
}

function labelCard(slide, ctx, label, body, x, y, w, h, opts = {}) {
  card(slide, ctx, x, y, w, h, opts);
  text(slide, ctx, label, x + 18, y + 16, w - 36, 22, {
    size: opts.labelSize ?? 12,
    color: opts.labelColor ?? C.teal,
    bold: true,
  });
  text(slide, ctx, body, x + 18, y + 45, w - 36, h - 58, {
    size: opts.bodySize ?? 14,
    color: opts.bodyColor ?? C.ink,
  });
}

function metric(slide, ctx, value, label, note, x, y, opts = {}) {
  vline(slide, ctx, x + (opts.rtl ? 154 : 0), y - 2, 58, opts.color ?? C.teal, 3);
  text(slide, ctx, value, x, y, 150, 34, {
    size: opts.valueSize ?? 28,
    color: opts.valueColor ?? C.ink,
    bold: true,
    align: opts.align ?? "right",
  });
  text(slide, ctx, label, x, y + 36, 150, 18, {
    size: 10,
    color: opts.labelColor ?? C.muted,
    bold: true,
    align: opts.align ?? "right",
  });
  text(slide, ctx, note, x, y + 54, 150, 26, {
    size: 8.5,
    color: opts.noteColor ?? C.muted,
    align: opts.align ?? "right",
  });
}

function pill(slide, ctx, value, x, y, w, fill, color = C.ink) {
  rect(slide, ctx, x, y, w, 28, fill, { stroke: "#00000000" });
  text(slide, ctx, value, x + 12, y + 5, w - 24, 18, { size: 10, color, bold: true, align: "center" });
}

function slide01(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "תוצר 2 | Research Proposal Project");
  title(slide, ctx, "הקצאת קורסים מודעת חברות: הצעת מחקר אמפירית", {
    x: 430,
    y: 112,
    w: 780,
    h: 104,
    size: 42,
  });
  sub(
    slide,
    ctx,
    "מנגנון HBS-style snake draft המשלב העדפות חברות מכוונות, תועלת חברתית ריאקטיבית וחיפוש מקומי לאחר ההקצאה.",
    470,
    244,
    735,
    54,
    { size: 16 },
  );

  rect(slide, ctx, 70, 96, 300, 422, C.dark);
  text(slide, ctx, "ליבת המחקר", 104, 126, 230, 24, { size: 12, color: "#C7D7EA", bold: true, dark: true });
  text(slide, ctx, "כאשר סטודנטים\nבוחרים גם עם מי\nללמוד", 104, 166, 230, 126, {
    size: 33,
    color: C.white,
    bold: true,
    dark: true,
  });
  text(
    slide,
    ctx,
    "הפרויקט בודק כיצד הכנסת קשרי חברות למנגנון הקצאה משנה רווחה, שביעות רצון חברתית, דירוגים והוגנות.",
    104,
    324,
    226,
    82,
    { size: 14, color: "#D9E2EF", dark: true },
  );
  pill(slide, ctx, "אמפירי-חישובי", 116, 438, 202, C.gold2, C.dark);

  metric(slide, ctx, "01", "מנגנון", "snake draft דטרמיניסטי", 912, 386, { color: C.teal, rtl: true });
  metric(slide, ctx, "02", "משתנה חברתי", "LambdaFriend אישי", 690, 386, { color: C.berry, rtl: true });
  metric(slide, ctx, "03", "ניתוח", "רווחה, הוגנות וחפיפות", 468, 386, { color: C.gold, rtl: true });

  card(slide, ctx, 434, 552, 735, 72, { fill: "#FFFCF4" });
  text(slide, ctx, "טענת המחקר", 1040, 570, 96, 18, { size: 10, color: C.teal, bold: true });
  text(
    slide,
    ctx,
    "התחשבות בהעדפות חברתיות יכולה להגדיל תועלת כוללת וחוויה חברתית, אך עשויה ליצור מחיר במדדי דירוג והוגנות.",
    486,
    568,
    530,
    42,
    { size: 15, color: C.ink, bold: true },
  );
  footer(slide, ctx, 1, "Sources: README.md; project_presentation_materials.txt");
  return slide;
}

function slide02(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "מבוא ורקע תאורטי");
  title(slide, ctx, "הפער: מנגנוני הקצאת קורסים מניחים לרוב העדפות בלתי תלויות.");
  sub(
    slide,
    ctx,
    "בפועל, סטודנט עשוי להעדיף קורס לא רק בגלל תוכן, מרצה או שעה, אלא גם בגלל חברים שילמדו איתו.",
    470,
    172,
    742,
    40,
  );

  labelCard(slide, ctx, "התופעה המחקרית", "הקצאת מקומות מוגבלים בקורסים היא בעיית assignment חד-צדדית: סטודנטים מקבלים חבילות קורסים תחת מגבלות קיבולת.", 852, 262, 310, 192, {
    labelColor: C.blue,
  });
  labelCard(slide, ctx, "פער ידע", "הספרות מתמקדת בהוגנות, יעילות, אסטרטגיה וקיבולת. רכיב הקשרים החברתיים בין סטודנטים כמעט אינו מופיע במודל ההקצאה עצמו.", 486, 262, 310, 192, {
    labelColor: C.berry,
  });
  labelCard(slide, ctx, "הצעת המחקר", "להוסיף שכבת social utility מכוונת ותלוית-קורס, ולבדוק את ההשפעה על רווחה, חפיפות חברים, דירוגים ואי-שוויון.", 120, 262, 310, 192, {
    labelColor: C.teal,
  });

  line(slide, ctx, 154, 515, 982, C.faint, 1);
  text(slide, ctx, "ניסוח הפער", 1016, 542, 120, 20, { size: 11, color: C.teal, bold: true });
  text(
    slide,
    ctx,
    "המחקר אינו שואל רק איזה מנגנון מקצה טוב יותר, אלא מה קורה כאשר ההעדפה עצמה היא חברתית ותלויה בתוצאת ההקצאה של אחרים.",
    240,
    538,
    754,
    44,
    { size: 17, bold: true },
  );
  footer(slide, ctx, 2, "Sources: local project materials; Budish & Cantillon 2012; Budish 2011");
  return slide;
}

function slide03(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "סקירת ספרות ממוקדת");
  title(slide, ctx, "הספרות מסבירה הקצאה הוגנת ויעילה, אך לא את התלות החברתית בין בחירות סטודנטים.", {
    size: 33,
  });

  const cols = [
    ["הקצאת קורסים", "multi-unit assignment, קיבולת, חבילות קורסים, HBS draft.\nעוגן: Budish & Cantillon."],
    ["מנגנוני הקצאה", "RSD, draft, A-CEEI, fair division, strategyproofness.\nעוגן: Budish; Abdulkadiroglu & Sonmez."],
    ["העדפות חברתיות", "תועלת אינה רק אישית: fairness, reciprocity, social welfare.\nעוגן: Fehr & Schmidt; Charness & Rabin."],
    ["הפער המוצע", "אין שכבה מפורשת של חברות מכוונת, תלוית-קורס וריאקטיבית בתוך מנגנון בחירת הקורסים."],
  ];
  const xs = [914, 638, 362, 86];
  cols.forEach((col, i) => {
    card(slide, ctx, xs[i], 236, 230, 270, { fill: i === 3 ? C.dark : "#FFFCF4", stroke: i === 3 ? C.dark : C.faint });
    text(slide, ctx, col[0], xs[i] + 18, 258, 194, 30, {
      size: 15,
      color: i === 3 ? C.gold2 : [C.blue, C.teal, C.gold, C.berry][i],
      bold: true,
      dark: i === 3,
    });
    text(slide, ctx, col[1], xs[i] + 18, 306, 194, 154, {
      size: 12.3,
      color: i === 3 ? "#D9E2EF" : C.ink,
      dark: i === 3,
    });
  });
  text(slide, ctx, "מסגרת תאורטית משולבת", 1018, 560, 126, 20, { size: 11, color: C.teal, bold: true });
  text(
    slide,
    ctx,
    "Mechanism design מספק את שפת ההקצאה; social preferences מספקות את ההצדקה לכך שהסטודנט מחשיב גם תוצאות של אחרים.",
    310,
    556,
    690,
    42,
    { size: 15.5, bold: true },
  );
  footer(slide, ctx, 3, "Literature anchors: course allocation, fair division, school choice, social preferences");
  return slide;
}

function slide04(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "שאלות והשערות מחקר");
  title(slide, ctx, "ההשערות מתמקדות ברווחה, תיווך חברתי, מחיר אישי ומיתון לפי תנאי שוק.");

  const rows = [
    ["RQ1", "כיצד שילוב העדפות חברות במנגנון ההקצאה משפיע על תועלת כוללת?", "H1", "שילוב social utility יעלה את התועלת הכוללת לעומת draft ללא שיפור, בעיקר כאשר קיימת צפיפות חברתית מספקת."],
    ["RQ2", "האם חפיפות חברים מתווכות את השפעת המנגנון על רווחה?", "H2", "ההשפעה של hybrid-global על רווחה תתווך חלקית דרך עלייה בחפיפות חברים בקורסים."],
    ["RQ3", "האם הרווח החברתי בא על חשבון דירוג אישי והוגנות?", "H3", "עלייה ברכיב החברתי תלווה בהחמרת דירוג ממוצע ובעלייה מתונה באי-שוויון."],
    ["RQ4", "מתי המנגנון יעיל יותר או פחות?", "H4", "השפעת המנגנון תמותן על ידי LambdaFriend, צפיפות רשת החברות ורמת לחץ הקיבולת."],
  ];
  rows.forEach((r, i) => {
    const y = 184 + i * 96;
    rect(slide, ctx, 1018, y, 64, 28, C.blue);
    text(slide, ctx, r[0], 1018, y + 5, 64, 18, { size: 10, color: C.white, bold: true, align: "center", dark: true });
    text(slide, ctx, r[1], 710, y, 290, 58, { size: 12.7, color: C.ink, bold: true });
    rect(slide, ctx, 582, y, 64, 28, C.teal);
    text(slide, ctx, r[2], 582, y + 5, 64, 18, { size: 10, color: C.white, bold: true, align: "center", dark: true });
    text(slide, ctx, r[3], 142, y, 420, 62, { size: 12.2, color: C.ink });
    line(slide, ctx, 132, y + 76, 982, C.faint, 1);
  });
  footer(slide, ctx, 4, "Research questions and hypotheses synthesized from model + preliminary computational evidence");
  return slide;
}

function slide05(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "מודל מחקר");
  title(slide, ctx, "המודל מחבר בין העדפות אישיות, העדפות חברות ומדדי תוצאה מרובי-ממד.");

  const rightX = 874;
  labelCard(slide, ctx, "משתני קלט", "דירוגי קורסים אישיים\nקשרי חברות מכוונים לפי קורס\nLambdaFriend אישי", rightX, 228, 286, 132, {
    labelColor: C.blue,
    bodySize: 13,
  });
  labelCard(slide, ctx, "מנגנון", "HBS-style snake draft\n+ תועלת חברתית ריאקטיבית\n+ tie-breaking דטרמיניסטי", 512, 228, 286, 132, {
    labelColor: C.teal,
    bodySize: 13,
  });
  labelCard(slide, ctx, "שיפור לאחר הקצאה", "swap / drop-add / hybrid\nobjective scope:\nglobal או personal", 150, 228, 286, 132, {
    labelColor: C.gold,
    bodySize: 13,
  });
  text(slide, ctx, "←", 810, 266, 44, 44, { size: 28, color: C.muted, align: "center" });
  text(slide, ctx, "←", 448, 266, 44, 44, { size: 28, color: C.muted, align: "center" });

  card(slide, ctx, 402, 420, 480, 84, { fill: C.dark, stroke: C.dark });
  text(slide, ctx, "תיווך: חפיפות חברים בפועל", 620, 442, 230, 22, { size: 13, color: C.gold2, bold: true, dark: true });
  text(slide, ctx, "האם השיפור ברווחה עובר דרך יותר חברים באותו קורס?", 436, 466, 398, 22, { size: 12.5, color: "#D9E2EF", dark: true });

  labelCard(slide, ctx, "תוצאות", "תועלת כוללת\nתועלת חברתית\nדירוג ממוצע / Top-3\nGini, Jain, Theil, Atkinson", 815, 528, 316, 112, {
    labelColor: C.teal,
    bodySize: 11.5,
  });
  labelCard(slide, ctx, "מיתון", "צפיפות רשת חברות\nלחץ קיבולת\nערכי LambdaFriend", 140, 528, 316, 112, {
    labelColor: C.berry,
    bodySize: 11.5,
  });
  footer(slide, ctx, 5, "Sources: README utility model; local experiment design");
  return slide;
}

function slide06(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "שיטת מחקר");
  title(slide, ctx, "מערך המחקר הוא ניסוי חישובי השוואתי עם חזרות לפי seed ופרמטרים מבוקרים.");

  const headers = ["גורם", "רמות / מניפולציה", "מטרת ההשוואה"];
  const rows = [
    ["מנגנון שיפור", "none, swap, drop-add, hybrid", "האם חיפוש מקומי משפר את draft הבסיסי"],
    ["יעד אופטימיזציה", "global מול personal", "הבחנה בין רווחה מערכתית לרווח אישי"],
    ["חוזק חברתי", "LambdaFriend: 0 עד 1", "בדיקת משקל ההעדפה החברתית"],
    ["תרחיש שוק", "מספר קורסים, קיבולות, צפיפות חברים", "בדיקת רגישות ותוקף חיצוני"],
  ];
  drawTable(slide, ctx, 116, 214, [210, 396, 430], 58, headers, rows);

  card(slide, ctx, 146, 564, 988, 68, { fill: "#FFFCF4" });
  text(slide, ctx, "יחידת ניתוח", 1020, 582, 88, 18, { size: 10, color: C.teal, bold: true });
  text(
    slide,
    ctx,
    "ריצה אחת של אלגוריתם מוגדרת על ידי תרחיש, seed, מצב שיפור, מספר איטרציות וערך LambdaFriend; המדדים מחושבים ברמת הריצה ומושווים בין תנאים.",
    188,
    580,
    812,
    40,
    { size: 13.5, bold: true },
  );
  footer(slide, ctx, 6, "Sources: generate/generate_tables.py; HBS/hbs_experiments.py; results/experiments");
  return slide;
}

function slide07(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "כלי מדידה, מהימנות ותוקף");
  title(slide, ctx, "מדידה חזקה דורשת להפריד בין איכות הקצאה, תועלת חברתית והוגנות.");

  const domains = [
    ["רווחה", "total_utility, avg_utility_per_student, total_base_utility", "פירוק לתועלת בסיס ותועלת חברים"],
    ["שביעות רצון חברתית", "avg_friend_overlaps_per_student, share_any_overlap", "תוקף מבנה: מודד את מימוש קשרי החברות"],
    ["שביעות רצון אישית", "avg_position, median_position, share_top1, share_top3", "בדיקת מחיר אישי של הרכיב החברתי"],
    ["הוגנות ואי-שוויון", "Gini, Jain, Theil, Atkinson, percentiles", "רגישות להתפלגות ולא רק לממוצע"],
  ];
  domains.forEach((d, i) => {
    const x = i < 2 ? 672 : 116;
    const y = i % 2 === 0 ? 226 : 416;
    card(slide, ctx, x, y, 492, 142, { fill: "#FFFCF4" });
    text(slide, ctx, d[0], x + 24, y + 20, 430, 24, { size: 15, color: [C.teal, C.blue, C.gold, C.berry][i], bold: true });
    text(slide, ctx, d[1], x + 24, y + 54, 430, 34, { size: 12.5, mono: true, color: C.ink });
    text(slide, ctx, d[2], x + 24, y + 100, 430, 24, { size: 12.5, color: C.muted });
  });
  text(slide, ctx, "מהימנות", 1044, 592, 90, 18, { size: 10, color: C.teal, bold: true });
  text(slide, ctx, "seed קבוע, tie-breaking דטרמיניסטי ו-44 בדיקות אוטומטיות שעברו בהצלחה.", 342, 588, 684, 28, {
    size: 14.5,
    bold: true,
  });
  footer(slide, ctx, 7, "Sources: README metrics; tests/run_all_tests.py; project materials");
  return slide;
}

function slide08(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "תוכנית ניתוח נתונים");
  title(slide, ctx, "הניתוח ישלב השוואות תנאים, מודלי רגרסיה, תיווך/מיתון ובדיקות איתנות.");

  const steps = [
    ["01", "תיאור ואימות", "סטטיסטיקות בסיס, התפלגויות, בדיקות קיבולת והיתכנות"],
    ["02", "בדיקת השערות", "השוואת תנאים: none מול מצבי שיפור, global מול personal"],
    ["03", "מודלים", "רגרסיה / mixed effects עם seed ותרחיש כגורמי בקרה"],
    ["04", "איתנות", "רגישות ל-LambdaFriend, צפיפות חברים, לחץ קיבולת ומספר איטרציות"],
  ];
  steps.forEach((s, i) => {
    const y = 204 + i * 82;
    rect(slide, ctx, 992, y, 54, 54, [C.blue, C.teal, C.gold, C.berry][i]);
    text(slide, ctx, s[0], 992, y + 14, 54, 22, { size: 15, color: C.white, bold: true, align: "center", dark: true });
    text(slide, ctx, s[1], 842, y + 5, 126, 22, { size: 14, color: C.ink, bold: true });
    text(slide, ctx, s[2], 332, y + 5, 482, 40, { size: 13, color: C.muted });
    if (i < steps.length - 1) vline(slide, ctx, 1018, y + 58, 24, C.faint, 2);
  });

  card(slide, ctx, 112, 214, 166, 272, { fill: C.dark, stroke: C.dark });
  text(slide, ctx, "עיקרון מתודולוגי", 136, 244, 118, 20, { size: 10, color: C.gold2, bold: true, dark: true });
  text(slide, ctx, "לא מסתפקים בממוצע אחד", 136, 282, 118, 56, { size: 22, color: C.white, bold: true, dark: true });
  text(slide, ctx, "נדרש להראות חזית טרייד-אוף בין רווחה, חברות, דירוג והוגנות.", 136, 372, 118, 72, {
    size: 12,
    color: "#D9E2EF",
    dark: true,
  });
  footer(slide, ctx, 8, "Analysis plan: repeated computational experiment; multi-metric outcome framework");
  return slide;
}

function slide09(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "ראיות ראשוניות");
  title(slide, ctx, "בתרחיש 200x8, hybrid-global תופס את רוב שיפור הרווחה בתוך חמש איטרציות.");

  text(slide, ctx, "שינוי ממוצע ב-total utility מול baseline ללא post-allocation", 688, 208, 444, 20, {
    size: 12,
    color: C.muted,
    bold: true,
  });
  DATA.gains.forEach((item, i) => gainBar(slide, ctx, item, 150, 262 + i * 66));

  card(slide, ctx, 872, 512, 246, 140, { fill: "#FFFCF4" });
  text(slide, ctx, "Baseline", 1002, 528, 86, 14, { size: 9, color: C.muted, bold: true });
  text(slide, ctx, "371.310", 932, 546, 156, 30, { size: 24, color: C.ink, bold: true, align: "right" });
  text(slide, ctx, "hybrid-global post=5", 944, 584, 144, 14, { size: 8.5, color: C.teal, bold: true });
  text(slide, ctx, "384.805", 886, 604, 202, 30, { size: 23, color: C.teal, bold: true });

  text(
    slide,
    ctx,
    "פירוש זהיר: אלה ראיות חישוביות ראשוניות ממערך סינתטי, שמראות כיוון ואפקטיביות של המנגנון אך אינן מחליפות בדיקה על נתוני אמת.",
    142,
    574,
    600,
    44,
    { size: 13.5, color: C.muted },
  );
  footer(slide, ctx, 9, "Source: results/experiments/A_200x8_mode_post_agg_partial.csv; seeds 11-20");
  return slide;
}

function slide10(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "מחיר ותמורה");
  title(slide, ctx, "הרווח החברתי מלווה בטרייד-אוף מול דירוג אישי ואי-שוויון.");

  DATA.tradeoffs.forEach((d, i) => {
    const x = i < 2 ? 666 : 118;
    const y = i % 2 === 0 ? 226 : 404;
    tradeCard(slide, ctx, d, x, y);
  });

  card(slide, ctx, 414, 570, 452, 62, { fill: C.dark, stroke: C.dark });
  text(slide, ctx, "המשמעות להשערות", 708, 586, 126, 18, { size: 10, color: C.gold2, bold: true, dark: true });
  text(slide, ctx, "H2 נתמכת ככיוון ראשוני; H3 מגדירה את מחיר הרווח החברתי שיש למדוד ולאזן.", 442, 584, 250, 34, {
    size: 13,
    color: C.white,
    dark: true,
  });
  footer(slide, ctx, 10, "Source: local A_200x8 preliminary metrics from project_presentation_materials.txt");
  return slide;
}

function slide11(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "תרומה מחקרית צפויה");
  title(slide, ctx, "התרומה היא מודל מדיד להעדפות חברתיות בתוך מנגנון הקצאה.");

  labelCard(slide, ctx, "תרומה תאורטית", "הרחבת בעיית course allocation ממודל של העדפות בלתי תלויות למודל assignment חברתי עם תלות בין תוצאות סטודנטים.", 850, 236, 300, 224, {
    labelColor: C.teal,
    bodySize: 14,
  });
  labelCard(slide, ctx, "תרומה מתודולוגית", "מסגרת ניסויית שמפרידה בין מנגנון, יעד אופטימיזציה, משקל חברתי, מדדי רווחה ומדדי הוגנות.", 490, 236, 300, 224, {
    labelColor: C.blue,
    bodySize: 14,
  });
  labelCard(slide, ctx, "השלכות למחקר עתידי", "בדיקה עם נתוני אמת, סקרי העדפות, אילוצי מערכת שעות, פרטיות, וניתוח אסטרטגי של דיווח העדפות חברתיות.", 130, 236, 300, 224, {
    labelColor: C.gold,
    bodySize: 14,
  });

  text(slide, ctx, "לא רק שיפור אלגוריתמי", 954, 548, 196, 24, { size: 13, color: C.berry, bold: true });
  text(slide, ctx, "המחקר מציע שפה אמפירית למדידת המחיר והתועלת של הכנסת קשרים חברתיים למנגנוני הקצאה מוסדיים.", 240, 544, 688, 44, {
    size: 16,
    bold: true,
  });
  footer(slide, ctx, 11, "Contribution synthesized from proposal structure and local prototype");
  return slide;
}

function slide12(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx, true);
  kicker(slide, ctx, "איתנות והגבלות המחקר", true);
  title(slide, ctx, "השלב הבא הוא להעביר את המודל מהוכחת היתכנות לניסוי מחקרי מלא.", {
    dark: true,
    size: 34,
  });

  const items = [
    ["הגבלה", "הנתונים הנוכחיים סינתטיים ולכן אינם מוכיחים תוקף חיצוני על אוכלוסיית סטודנטים אמיתית."],
    ["איתנות", "יש להריץ מטריצת תרחישים רחבה: צפיפות חברים, קיבולות, ערכי Lambda, מספר seeds ומספר איטרציות."],
    ["תוקף", "נדרש לשלב סקר או נתוני העדפות אמיתיים ולבחון האם קשרי חברות מדווחים מתנהגים כמו המודל."],
    ["אתיקה ופרטיות", "העדפות חברות הן מידע רגיש; מחקר המשך ידרוש אנונימיזציה, הסכמה ושמירה על מידע אישי."],
  ];
  items.forEach((item, i) => {
    const x = i < 2 ? 666 : 118;
    const y = i % 2 === 0 ? 220 : 404;
    rect(slide, ctx, x, y, 486, 132, "#223044", { stroke: "#41516A", weight: 1 });
    text(slide, ctx, item[0], x + 26, y + 22, 420, 22, { size: 14, color: i === 0 ? C.berry2 : C.gold2, bold: true, dark: true });
    text(slide, ctx, item[1], x + 26, y + 56, 420, 50, { size: 13, color: "#D9E2EF", dark: true });
  });
  text(slide, ctx, "סיום", 1066, 594, 64, 18, { size: 10, color: C.gold2, bold: true, dark: true });
  text(slide, ctx, "הצעת המחקר עומדת על טרייד-אוף מדיד: יותר חוויה חברתית ורווחה מערכתית, מול עלות אפשרית בדירוג אישי ובהוגנות.", 304, 590, 740, 44, {
    size: 15.5,
    color: C.white,
    bold: true,
    dark: true,
  });
  footer(slide, ctx, 12, "Final slide: limitations, robustness plan, and next research steps", true);
  return slide;
}

function drawTable(slide, ctx, x, y, widths, rowH, headers, rows) {
  const totalW = widths.reduce((a, b) => a + b, 0);
  rect(slide, ctx, x, y, totalW, 42, C.dark, { stroke: C.dark });
  let cursor = x + totalW;
  headers.forEach((h, i) => {
    cursor -= widths[i];
    text(slide, ctx, h, cursor + 12, y + 12, widths[i] - 24, 18, { size: 11, color: C.white, bold: true, dark: true });
    if (i > 0) vline(slide, ctx, cursor + widths[i], y, 42 + rows.length * rowH, "#D7CDBE", 1);
  });
  rows.forEach((row, r) => {
    const yy = y + 42 + r * rowH;
    rect(slide, ctx, x, yy, totalW, rowH, r % 2 === 0 ? "#FFFCF4" : C.bg2, { stroke: C.faint, weight: 1 });
    let cx = x + totalW;
    row.forEach((cell, i) => {
      cx -= widths[i];
      text(slide, ctx, cell, cx + 12, yy + 12, widths[i] - 24, rowH - 28, {
        size: i === 0 ? 12.5 : 12,
        color: i === 0 ? C.teal : C.ink,
        bold: i === 0,
      });
    });
  });
}

function gainBar(slide, ctx, item, x, y) {
  const labelW = 294;
  const trackW = 370;
  const zero = x + labelW + 58;
  const scale = 76;
  text(slide, ctx, item.label, x + labelW + trackW - 130, y - 8, 424, 18, {
    size: 12,
    color: C.ink,
    bold: true,
    align: "right",
  });
  rect(slide, ctx, x + labelW, y + 28, trackW, 12, C.faint2);
  vline(slide, ctx, zero, y + 20, 30, C.muted, 1);
  if (item.value >= 0) {
    rect(slide, ctx, zero, y + 24, Math.max(3, item.value * scale), 20, item.color);
  } else {
    rect(slide, ctx, zero + item.value * scale, y + 24, Math.max(3, Math.abs(item.value) * scale), 20, item.color);
  }
  text(slide, ctx, `${item.value > 0 ? "+" : ""}${item.value.toFixed(2)}%`, x + labelW + trackW + 18, y + 24, 88, 24, {
    size: 15,
    color: item.color,
    bold: true,
    align: "right",
  });
}

function tradeCard(slide, ctx, item, x, y) {
  card(slide, ctx, x, y, 496, 154, { fill: "#FFFCF4" });
  text(slide, ctx, item.label, x + 24, y + 18, 440, 22, { size: 15, color: item.color, bold: true });
  text(slide, ctx, "לפני", x + 340, y + 58, 50, 16, { size: 9.5, color: C.muted, bold: true });
  text(slide, ctx, item.before, x + 258, y + 78, 132, 30, { size: 24, color: C.ink, bold: true });
  text(slide, ctx, "אחרי", x + 166, y + 58, 50, 16, { size: 9.5, color: C.muted, bold: true });
  text(slide, ctx, item.after, x + 76, y + 78, 140, 30, { size: 24, color: item.color, bold: true });
  text(slide, ctx, "←", x + 220, y + 76, 34, 28, { size: 20, color: C.muted, align: "center" });
  pill(slide, ctx, item.delta, x + 66, y + 112, 160, item.good ? C.teal2 : C.berry2, item.good ? C.teal : C.berry);
}
