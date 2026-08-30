import fs from 'node:fs/promises';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

const OUT = '/Users/lindsaybull/iac-league/Club-League-Portal-Prospectus.pptx';
const LOGO = '/Users/lindsaybull/iac-league/tmp/prospectus/irene-logo.png';
const W = 1280, H = 720;
const C = { ink: '#18352B', green: '#287D42', lime: '#49B45B', mint: '#EAF6EF', aqua: '#79CEC3', brown: '#743136', line: '#CFE5D7', gray: '#5C6B64', pale: '#F7FBF8', white: '#FFFFFF' };

async function save(blob, path) { await fs.writeFile(path, new Uint8Array(await blob.arrayBuffer())); }
function shape(slide, geometry, left, top, width, height, fill = 'none', line = 'none') {
  return slide.shapes.add({ geometry, position: { left, top, width, height }, fill, line: { style: 'solid', fill: line, width: line === 'none' ? 0 : 1 } });
}
function text(slide, value, left, top, width, height, style = {}) {
  const box = shape(slide, 'textbox', left, top, width, height);
  box.text = value;
  box.text.style = { fontFace: 'Aptos', fontSize: 22, color: C.ink, breakLine: false, ...style };
  return box;
}
function rule(slide, left, top, width, color = C.lime, h = 5) { shape(slide, 'rect', left, top, width, h, color); }
function footer(slide, n) {
  text(slide, 'CLUB LEAGUE PORTAL  |  PROSPECTUS', 72, 678, 420, 16, { fontSize: 10, bold: true, color: C.green, characterSpacing: 1 });
  text(slide, String(n).padStart(2, '0'), 1168, 678, 40, 16, { fontSize: 10, bold: true, color: C.green, alignment: 'right' });
}
function bullet(slide, title, body, x, y, number) {
  shape(slide, 'ellipse', x, y + 2, 34, 34, C.green);
  text(slide, String(number), x, y + 8, 34, 20, { fontSize: 15, bold: true, color: C.white, alignment: 'center' });
  text(slide, title, x + 54, y, 390, 27, { fontSize: 22, bold: true, color: C.ink });
  text(slide, body, x + 54, y + 33, 410, 54, { fontSize: 16, color: C.gray, breakLine: true, lineSpacing: 1.1 });
}
function addLogo(slide, left = 1040, top = 45, w = 125, h = 90) {
  // The prospectus remains intentionally club-neutral; each client receives their own branding at implementation.
}

const deck = Presentation.create({ slideSize: { width: W, height: H } });

// 1 - Cover
{
  const s = deck.slides.add(); s.background.fill = C.pale;
  shape(s, 'rect', 0, 0, 390, H, C.green);
  shape(s, 'rect', 390, 0, 14, H, C.aqua);
  text(s, 'CLUB LEAGUE PORTAL', 72, 78, 240, 22, { fontSize: 13, bold: true, color: C.white, characterSpacing: 2 });
  text(s, 'An easier way\nto run your\nclub league.', 72, 150, 290, 250, { fontSize: 51, bold: true, color: C.white, breakLine: true, lineSpacing: 0.9 });
  text(s, 'A practical, branded league portal - ready to make your results clearer for every athlete.', 72, 454, 250, 90, { fontSize: 18, color: '#E6F6EB', breakLine: true, lineSpacing: 1.2 });
  rule(s, 474, 126, 98, C.lime, 7);
  text(s, 'Your club gets one clear\nplace for results, points\nand progress.', 474, 164, 710, 165, { fontSize: 44, bold: true, color: C.ink, breakLine: true, lineSpacing: 0.95 });
  text(s, 'Pricing & implementation prospectus', 478, 355, 420, 28, { fontSize: 21, color: C.gray });
  shape(s, 'roundRect', 474, 438, 614, 128, C.white, C.line);
  text(s, 'IMPLEMENTATION', 505, 464, 170, 18, { fontSize: 12, bold: true, color: C.green, characterSpacing: 1 });
  text(s, 'R12,500', 505, 492, 210, 48, { fontSize: 35, bold: true, color: C.ink });
  text(s, 'Live in approximately 5 working days*', 760, 500, 285, 28, { fontSize: 18, bold: true, color: C.green, alignment: 'right' });
  text(s, '*From receipt of the agreed information and files.', 478, 608, 450, 18, { fontSize: 12, color: C.gray });
  addLogo(s, 1084, 580, 100, 70);
}

// 2 - Why it matters
{
  const s = deck.slides.add(); s.background.fill = C.white; footer(s, 2); addLogo(s);
  text(s, 'Your league should not live in spreadsheets and WhatsApp messages.', 72, 70, 940, 82, { fontSize: 39, bold: true, color: C.ink, breakLine: true, lineSpacing: 0.96 });
  rule(s, 72, 173, 82);
  text(s, 'The portal gives athletes a reliable, public view of the league while keeping result administration simple for the club.', 72, 208, 960, 54, { fontSize: 21, color: C.gray, breakLine: true });
  shape(s, 'rect', 72, 314, 350, 242, C.mint);
  text(s, 'For athletes', 104, 347, 220, 30, { fontSize: 25, bold: true, color: C.green });
  text(s, 'See current rank, points, race history and the next person to chase.', 104, 399, 265, 90, { fontSize: 20, color: C.ink, breakLine: true, lineSpacing: 1.15 });
  shape(s, 'rect', 466, 314, 350, 242, '#F3F8F5');
  text(s, 'For administrators', 498, 347, 255, 30, { fontSize: 25, bold: true, color: C.green });
  text(s, 'Upload results, recalculate automatically and keep one consistent points table.', 498, 399, 270, 90, { fontSize: 20, color: C.ink, breakLine: true, lineSpacing: 1.15 });
  shape(s, 'rect', 860, 314, 348, 242, '#E7F7F5');
  text(s, 'For the club', 892, 347, 205, 30, { fontSize: 25, bold: true, color: C.green });
  text(s, 'A club-branded home for the league that is ready to share with members.', 892, 399, 265, 90, { fontSize: 20, color: C.ink, breakLine: true, lineSpacing: 1.15 });
}

// 3 - What the club receives
{
  const s = deck.slides.add(); s.background.fill = C.pale; footer(s, 3); addLogo(s);
  text(s, 'What your club receives', 72, 70, 600, 48, { fontSize: 42, bold: true });
  text(s, 'The core system is already built and working. Your implementation configures it for your club.', 72, 130, 865, 35, { fontSize: 20, color: C.gray });
  bullet(s, 'Public leaderboards', 'Separate Run and Walk views, clear rankings and a current league overview.', 74, 225, 1);
  bullet(s, 'Athlete profiles', 'Individual pages show race history, finish times, points and close rivals.', 74, 362, 2);
  bullet(s, 'Protected result uploads', 'An authorised administrator uploads CSV or Excel results and the table recalculates.', 650, 225, 3);
  bullet(s, 'Transparent points rules', 'A public points page makes the scoring approach easy for athletes to understand.', 650, 362, 4);
  shape(s, 'roundRect', 72, 536, 1136, 88, C.white, C.line);
  text(s, 'Built for a club league, not a generic race-results website.', 106, 563, 790, 28, { fontSize: 24, bold: true, color: C.green });
  text(s, 'Simple for members. Manageable for your committee.', 106, 593, 630, 18, { fontSize: 16, color: C.gray });
}

// 4 - Implementation
{
  const s = deck.slides.add(); s.background.fill = C.white; footer(s, 4); addLogo(s);
  text(s, 'Implementation: allow 5 working days.', 72, 70, 970, 50, { fontSize: 40, bold: true });
  text(s, 'We allow enough time to set up the league properly, check the data and hand it over with confidence.', 72, 136, 900, 32, { fontSize: 19, color: C.gray });
  const steps = [
    ['Day 1', 'Set-up', 'Receive branding, rules, categories and sample results.'],
    ['Day 2', 'Configure', 'Apply club identity and points configuration.'],
    ['Days 3-4', 'Validate', 'Import results, resolve file issues and test the rankings.'],
    ['Day 5', 'Launch', 'Deploy, check access and hand over the upload process.'],
  ];
  let x = 72;
  for (let i = 0; i < steps.length; i++) {
    if (i) shape(s, 'rect', x - 24, 358, 34, 4, C.aqua);
    shape(s, 'ellipse', x, 318, 86, 86, i === 3 ? C.green : C.mint, i === 3 ? C.green : C.line);
    text(s, String(i + 1), x, 341, 86, 24, { fontSize: 22, bold: true, color: i === 3 ? C.white : C.green, alignment: 'center' });
    text(s, steps[i][0], x, 435, 210, 20, { fontSize: 13, bold: true, color: C.green, characterSpacing: 1 });
    text(s, steps[i][1], x, 465, 220, 28, { fontSize: 24, bold: true });
    text(s, steps[i][2], x, 508, 220, 75, { fontSize: 16, color: C.gray, breakLine: true, lineSpacing: 1.12 });
    x += 290;
  }
  text(s, 'Timing assumes the required information is supplied promptly and the initial historical data is in CSV or XLSX format.', 72, 625, 1020, 22, { fontSize: 14, color: C.gray });
}

// 5 - Price and boundaries
{
  const s = deck.slides.add(); s.background.fill = C.pale; footer(s, 5); addLogo(s);
  text(s, 'A clear, fixed-price starting point', 72, 70, 800, 48, { fontSize: 42, bold: true });
  shape(s, 'roundRect', 72, 162, 482, 385, C.green);
  text(s, 'IMPLEMENTATION', 112, 208, 220, 20, { fontSize: 13, bold: true, color: '#DDF5E4', characterSpacing: 2 });
  text(s, 'R12,500', 112, 250, 310, 72, { fontSize: 58, bold: true, color: C.white });
  text(s, 'Once-off setup for one club.', 112, 336, 280, 28, { fontSize: 20, color: C.white });
  rule(s, 112, 385, 330, C.aqua, 3);
  text(s, 'Includes configuration, historical result import, testing, deployment and a handover session.', 112, 419, 335, 75, { fontSize: 17, color: '#E7F6EB', breakLine: true, lineSpacing: 1.15 });
  text(s, 'ONGOING HOSTING & SUPPORT', 648, 190, 350, 20, { fontSize: 13, bold: true, color: C.green, characterSpacing: 1 });
  text(s, 'R500 / month', 648, 230, 395, 48, { fontSize: 37, bold: true, color: C.ink });
  text(s, 'For hosting, basic support and the day-to-day running of the portal.', 648, 298, 440, 52, { fontSize: 18, color: C.gray, breakLine: true });
  rule(s, 648, 383, 450, C.line, 2);
  text(s, 'The fixed implementation includes', 648, 420, 420, 26, { fontSize: 22, bold: true });
  text(s, '• One club-branded portal\n• Current feature set\n• One branding review\n• CSV/XLSX result files', 648, 462, 390, 100, { fontSize: 17, color: C.gray, breakLine: true, lineSpacing: 1.3 });
  text(s, 'Custom functionality, major historical data clean-up and non-standard scoring are scoped separately before work begins.', 72, 594, 1110, 36, { fontSize: 15, color: C.gray, breakLine: true });
}

// 6 - What we need
{
  const s = deck.slides.add(); s.background.fill = C.white; footer(s, 6); addLogo(s);
  text(s, 'What we need from your club to get started', 72, 70, 890, 50, { fontSize: 40, bold: true });
  text(s, 'Nothing complicated - just the information that makes the league yours.', 72, 130, 750, 28, { fontSize: 19, color: C.gray });
  const items = [
    ['1', 'Club identity', 'Logo, preferred colours and the public name of your league.'],
    ['2', 'League rules', 'Points tables, age categories, run/walk requirements and season approach.'],
    ['3', 'Race results', 'Historical and current results in CSV or Excel format where possible.'],
    ['4', 'Club contact', 'One person to answer questions and approve the final set-up.'],
  ];
  let y = 218;
  for (const item of items) {
    text(s, item[0], 78, y, 42, 34, { fontSize: 27, bold: true, color: C.lime });
    text(s, item[1], 150, y, 260, 28, { fontSize: 24, bold: true });
    text(s, item[2], 446, y + 3, 640, 42, { fontSize: 18, color: C.gray, breakLine: true });
    shape(s, 'rect', 72, y + 76, 1020, 1, C.line);
    y += 102;
  }
  shape(s, 'roundRect', 72, 623, 1020, 42, C.mint);
  text(s, 'If your files need attention, we will flag it early and agree the additional work before continuing.', 94, 634, 965, 18, { fontSize: 15, bold: true, color: C.green });
}

// 7 - Close
{
  const s = deck.slides.add(); s.background.fill = C.green;
  shape(s, 'rect', 0, 0, 620, H, '#236D3B');
  text(s, 'READY WHEN\nYOUR CLUB IS.', 72, 88, 470, 128, { fontSize: 55, bold: true, color: C.white, breakLine: true, lineSpacing: 0.9 });
  text(s, 'A clear league view is one of the simplest ways to keep members engaged and your committee in control.', 72, 268, 430, 90, { fontSize: 21, color: '#E3F6E9', breakLine: true, lineSpacing: 1.18 });
  rule(s, 72, 410, 108, C.aqua, 6);
  text(s, 'Next step', 72, 449, 200, 24, { fontSize: 17, bold: true, color: C.white });
  text(s, 'Send through your logo, points rules and a sample result file. We will confirm the implementation date and get the portal underway.', 72, 485, 450, 90, { fontSize: 18, color: '#E3F6E9', breakLine: true, lineSpacing: 1.18 });
  text(s, 'Club League Portal', 696, 132, 400, 34, { fontSize: 28, bold: true, color: C.white });
  text(s, 'A practical league portal, built around the way clubs actually work.', 696, 190, 420, 56, { fontSize: 20, color: '#DFF4E6', breakLine: true });
  shape(s, 'roundRect', 696, 312, 385, 168, '#EAF6EF');
  text(s, 'IMPLEMENTATION', 732, 342, 205, 18, { fontSize: 12, bold: true, color: C.green, characterSpacing: 1 });
  text(s, 'R12,500', 732, 378, 245, 46, { fontSize: 37, bold: true, color: C.ink });
  text(s, 'Allow 5 working days', 732, 435, 245, 20, { fontSize: 16, bold: true, color: C.green });
  addLogo(s, 1090, 560, 110, 82);
  text(s, 'Pricing & implementation prospectus', 696, 595, 340, 18, { fontSize: 13, color: '#DFF4E6' });
}

const pptx = await PresentationFile.exportPptx(deck);
await pptx.save(OUT);
for (let i = 0; i < deck.slides.items.length; i++) {
  await save(await deck.export({ slide: deck.slides.items[i], format: 'png', scale: 1 }), `/Users/lindsaybull/iac-league/tmp/prospectus/slide-${i + 1}.png`);
}
await save(await deck.export({ format: 'webp', montage: true, scale: 1 }), '/Users/lindsaybull/iac-league/tmp/prospectus/montage.webp');
