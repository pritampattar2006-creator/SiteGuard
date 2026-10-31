// The employee complaint report: one PDF that says, without needing anything else, who the employee is, which violations a supervisor confirmed (with the
// picture of the person, the place and the time), what fines follow from them, and what is still only an alert. It is a plain account of the records.
import PDFDocument from 'pdfkit';

const COUNTED = ['Confirmed', 'Acknowledged', 'Disputed'];
const INK = '#17202b', MUTED = '#586374', LINE = '#c9d0da', BAD = '#b42318', OK = '#067647', WARN = '#b54708', BRAND = '#1d4ed8', SOFT = '#f3f5f8';
const M = 40; // page margin
const WHEN = { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true };
const when = (iso) => (iso ? `${new Date(iso).toLocaleString('en-IN', WHEN)} IST` : '-');
const day = (iso) => (iso ? new Date(iso).toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' }) : '-');
const money = (n, cur = 'INR') => `${cur} ${Number(n || 0).toLocaleString('en-IN')}`;
const SOURCE = { 'live camera': 'Live camera', video: 'Video', 'photo upload': 'Photo', cctv: 'CCTV camera', demo: 'Demo data', 'phone camera': 'Phone camera' };

// "NO HELMET, NO VEST" -> "No helmet and no vest"
export const plainMissing = (missing) => {
  const items = String(missing || '').split(/\s*[,+]\s*/).filter(Boolean).map((s) => s.toLowerCase().replace(/^no /, 'no '));
  if (!items.length) return 'Not stated';
  const text = items.length === 1 ? items[0] : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
  return text.charAt(0).toUpperCase() + text.slice(1);
};
const STATUS_TEXT = {
  Confirmed: 'Confirmed by the supervisor. Waiting for the employee to reply.',
  Acknowledged: 'Confirmed by the supervisor. The employee acknowledged it.',
  Disputed: 'Confirmed by the supervisor. The employee disputed it and it is under review.',
  'Pending review': 'Not confirmed yet. This is only an alert.',
};
const PENALTY_TEXT = { Proposed: 'Proposed. Not a fine until a supervisor issues it.', Issued: 'Issued', Paid: 'Issued and paid', Waived: 'Waived. Nothing to pay.', Disputed: 'Issued, but disputed by the employee. Under review.' };

export function buildEmployeeReport({ employee, violations, pending, dismissedCount, penalties, policy, readUpload, preparedBy, now = new Date() }) {
  const doc = new PDFDocument({ size: 'A4', margin: M, bufferPages: true, info: { Title: `Employee complaint report - ${employee.name} (${employee.employeeId})`, Author: 'SiteGuard', Subject: 'PPE compliance complaint report' } });
  const W = doc.page.width - 2 * M;
  const bottom = () => doc.page.height - M - 24;
  const need = (h) => { if (doc.y + h > bottom()) doc.addPage(); };
  const rule = () => { doc.moveTo(M, doc.y).lineTo(M + W, doc.y).lineWidth(0.7).strokeColor(LINE).stroke(); doc.moveDown(0.4); };
  const heading = (text) => { need(60); doc.moveDown(0.6); doc.font('Helvetica-Bold').fontSize(12.5).fillColor(BRAND).text(text, M, doc.y); doc.moveDown(0.15); rule(); };
  const para = (text, opts = {}) => doc.font(opts.bold ? 'Helvetica-Bold' : 'Helvetica').fontSize(opts.size || 9.5).fillColor(opts.color || INK).text(text, M, doc.y, { width: W, ...opts.extra });
  const row = (label, value, color = INK) => {
    const y = doc.y;
    doc.font('Helvetica-Bold').fontSize(9).fillColor(MUTED).text(label, M, y, { width: 118 });
    doc.font('Helvetica').fontSize(9.5).fillColor(color).text(String(value || '-'), M + 122, y, { width: W - 122 });
    doc.y = Math.max(doc.y, y + 12);
  };
  const picture = (buf, x, y, w, h, caption) => {
    doc.rect(x, y, w, h).fillAndStroke(SOFT, LINE);
    if (buf) { try { doc.image(buf, x + 2, y + 2, { fit: [w - 4, h - 4], align: 'center', valign: 'center' }); } catch { doc.font('Helvetica').fontSize(8).fillColor(MUTED).text('Picture could not be shown', x, y + h / 2 - 4, { width: w, align: 'center' }); } }
    else doc.font('Helvetica').fontSize(8).fillColor(MUTED).text('No picture saved', x, y + h / 2 - 4, { width: w, align: 'center' });
    doc.font('Helvetica').fontSize(7.5).fillColor(MUTED).text(caption, x, y + h + 3, { width: w, align: 'center' });
  };

  // ---- title band ----
  doc.rect(0, 0, doc.page.width, 78).fill('#0f1b28');
  doc.font('Helvetica-Bold').fontSize(19).fillColor('#ffffff').text('Employee Safety Complaint Report', M, 20);
  doc.font('Helvetica').fontSize(9.5).fillColor('#b9c6d4').text('SiteGuard - PPE compliance (helmet and safety vest)', M, 46);
  doc.font('Helvetica').fontSize(9).fillColor('#b9c6d4').text(`Report no. ${employee.employeeId}-${now.toISOString().slice(0, 10).replace(/-/g, '')}`, M, 24, { width: W, align: 'right' });
  doc.text(`Prepared ${when(now)}`, M, 38, { width: W, align: 'right' });
  doc.text(`By ${preparedBy}`, M, 52, { width: W, align: 'right' });
  doc.y = 96;

  // ---- 1. the employee ----
  heading('1. Employee');
  const top = doc.y;
  const photoBuf = employee.photo && /^data:image\/(jpeg|png);base64,/.test(employee.photo) ? Buffer.from(employee.photo.split(',')[1], 'base64') : null;
  picture(photoBuf, M, top, 92, 112, photoBuf ? 'Employee photo' : 'No photo on file');
  const textX = M + 108;
  doc.y = top;
  const rowAt = (label, value) => { const y = doc.y; doc.font('Helvetica-Bold').fontSize(9).fillColor(MUTED).text(label, textX, y, { width: 100 }); doc.font('Helvetica').fontSize(10).fillColor(INK).text(String(value || '-'), textX + 104, y, { width: W - 108 - 104 }); doc.y = Math.max(doc.y, y + 14); };
  doc.font('Helvetica-Bold').fontSize(15).fillColor(INK).text(employee.name, textX, top, { width: W - 108 });
  doc.y = top + 24;
  rowAt('Employee ID', employee.employeeId);
  rowAt('Work role', employee.jobRole);
  rowAt('Sector', employee.sectorName);
  rowAt('Field / class', [employee.field, employee.className].filter(Boolean).join(' / '));
  rowAt('Supervisor', employee.supervisorName);
  doc.y = Math.max(doc.y, top + 112 + 24);  // below the photo and its caption

  // ---- 2. summary ----
  const windowMs = (policy.windowDays || 30) * 86400000;
  const recent = violations.filter((v) => now - new Date(v.occurredAt) <= windowMs).length;
  const finesIssued = penalties.filter((p) => ['Issued', 'Paid', 'Disputed'].includes(p.status));
  const finesTotal = finesIssued.reduce((s, p) => s + (p.amount || 0), 0);
  const waiting = penalties.filter((p) => p.status === 'Proposed');
  heading('2. Summary');
  const boxes = [
    [String(violations.length), 'Violations confirmed by a supervisor', violations.length ? BAD : OK],
    [String(recent), `of them in the last ${policy.windowDays} days`, recent >= policy.proposeAt ? BAD : recent ? WARN : OK],
    [money(finesTotal, policy.currency), `Fines issued (${finesIssued.length})`, finesTotal ? BAD : OK],
    [String(pending.length), 'Alerts not yet confirmed', pending.length ? WARN : OK],
  ];
  const bw = (W - 3 * 8) / 4, by = doc.y;
  boxes.forEach(([big, small, color], i) => {
    const x = M + i * (bw + 8);
    doc.rect(x, by, bw, 50).fillAndStroke('#ffffff', LINE);
    doc.font('Helvetica-Bold').fontSize(16).fillColor(color).text(big, x + 6, by + 7, { width: bw - 12 });
    doc.font('Helvetica').fontSize(7.5).fillColor(MUTED).text(small, x + 6, by + 30, { width: bw - 12 });
  });
  doc.y = by + 60;
  const sentence = violations.length
    ? `${employee.name} has ${violations.length} violation${violations.length > 1 ? 's' : ''} confirmed by a supervisor, ${recent} in the last ${policy.windowDays} days. ${finesTotal ? `Fines issued so far total ${money(finesTotal, policy.currency)}.` : 'No fine has been issued.'}${waiting.length ? ` ${waiting.length} fine${waiting.length > 1 ? 's are' : ' is'} proposed and waiting for a supervisor's decision.` : ''}`
    : `${employee.name} has no violations confirmed by a supervisor.`;
  para(sentence);
  doc.moveDown(0.3);
  para(`How fines work: ${policy.proposeAt} confirmed violations within ${policy.windowDays} days lead the system to PROPOSE a fine of ${money(policy.amount, policy.currency)}. The system never issues a fine by itself: a supervisor decides, and the employee can dispute it. A camera catch is only an alert until a supervisor confirms it.`, { size: 8.5, color: MUTED });

  // ---- 3. confirmed violations ----
  heading(`3. Confirmed violations (${violations.length})`);
  if (!violations.length) para('None.', { color: MUTED });
  violations.forEach((v, i) => {
    need(268);
    const y0 = doc.y;
    doc.rect(M, y0, W, 20).fill(SOFT);
    doc.font('Helvetica-Bold').fontSize(10).fillColor(INK).text(`Violation ${String(v.number).padStart(5, '0')}   -   ${when(v.occurredAt)}`, M + 8, y0 + 5, { width: W - 16 });
    doc.y = y0 + 26;
    row('What was missing', plainMissing(v.missing), BAD);
    row('Place', v.location || 'Not recorded');
    row('How it was caught', SOURCE[v.source] || v.source || '-');
    if (v.catches > 1) row('Times caught that day', `${v.catches} (counted as one violation for the day)`);
    row('Status', STATUS_TEXT[v.status] || v.status, v.status === 'Disputed' ? WARN : INK);
    row('Confirmed by', v.reviewedBy ? `${v.reviewedBy}, ${when(v.reviewedAt)}` : '-');
    const reply = (v.log || []).filter((l) => ['Acknowledged', 'Disputed'].includes(l.action)).pop();
    if (reply) row('Employee reply', `${reply.action}${reply.note ? `: "${reply.note}"` : ''}`);
    if (v.remarks) row('Remark', v.remarks);
    doc.moveDown(0.3);
    const py = doc.y, pw = (W - 12) / 2, ph = 150;
    picture(readUpload(v.evidencePath), M, py, pw, ph, 'The person (close-up)');
    picture(readUpload(v.contextPath) || null, M + pw + 12, py, pw, ph, 'Whole picture where it was caught (not saved for this case if blank)');
    doc.y = py + ph + 18;
    if (i < violations.length - 1) { rule(); }
  });

  // ---- 4. fines ----
  heading(`4. Fines and penalties (${penalties.length})`);
  if (!penalties.length) para('No fine has been proposed or issued.', { color: MUTED });
  else {
    const cols = [{ t: 'Date', w: 70 }, { t: 'Reason', w: W - 70 - 80 - 150 }, { t: 'Amount', w: 80 }, { t: 'Status', w: 150 }];
    let y = doc.y;
    doc.rect(M, y, W, 16).fill(SOFT);
    let x = M; cols.forEach((c) => { doc.font('Helvetica-Bold').fontSize(8.5).fillColor(MUTED).text(c.t, x + 4, y + 4, { width: c.w - 8 }); x += c.w; });
    y += 18;
    penalties.forEach((p) => {
      const cells = [day(p.createdAt), p.reason || '-', money(p.amount, p.currency || policy.currency), `${PENALTY_TEXT[p.status] || p.status}${p.decidedBy ? ` (${p.decidedBy})` : ''}${p.note ? `. Note: ${p.note}` : ''}`];
      const h = Math.max(...cells.map((c, i) => doc.font('Helvetica').fontSize(8.5).heightOfString(c, { width: cols[i].w - 8 }))) + 8;
      if (y + h > bottom()) { doc.addPage(); y = doc.y; }
      let cx = M; cells.forEach((c, i) => { doc.font(i === 2 ? 'Helvetica-Bold' : 'Helvetica').fontSize(8.5).fillColor(INK).text(c, cx + 4, y + 4, { width: cols[i].w - 8 }); cx += cols[i].w; });
      y += h; doc.moveTo(M, y).lineTo(M + W, y).lineWidth(0.4).strokeColor(LINE).stroke();
    });
    doc.y = y + 6;
    para(`Total of fines issued or disputed: ${money(finesTotal, policy.currency)}. Proposed fines are not included until a supervisor issues them.`, { bold: true, size: 9 });
  }

  // ---- 5. alerts not confirmed ----
  heading(`5. Alerts not yet confirmed (${pending.length})`);
  para('These were caught by a camera but no supervisor has confirmed them. They are NOT violations and carry NO fine unless a supervisor confirms them.', { size: 8.5, color: MUTED });
  doc.moveDown(0.3);
  if (!pending.length) para('None.', { color: MUTED });
  pending.forEach((v) => { need(16); para(`${when(v.occurredAt)}   |   ${plainMissing(v.missing)}   |   ${v.location || 'place not recorded'}`, { size: 9 }); });
  if (dismissedCount) { doc.moveDown(0.3); para(`${dismissedCount} earlier alert${dismissedCount > 1 ? 's were' : ' was'} dismissed by a supervisor as a false alarm and ${dismissedCount > 1 ? 'are' : 'is'} not counted.`, { size: 8.5, color: MUTED }); }

  // ---- 6. sign-off ----
  need(150);
  heading('6. Acknowledgement and right to dispute');
  para('The employee may dispute any confirmed violation or fine with a written reason, in the employee portal or to the supervisor. A disputed item is looked at again by a supervisor before anything is collected.', { size: 9 });
  doc.moveDown(1.6);
  const sy = doc.y, sw = (W - 24) / 2;
  [['Supervisor (name and signature)', 0], ['Employee (name and signature)', 1]].forEach(([label, k]) => {
    const x = M + k * (sw + 24);
    doc.moveTo(x, sy + 24).lineTo(x + sw, sy + 24).lineWidth(0.7).strokeColor(INK).stroke();
    doc.font('Helvetica').fontSize(8.5).fillColor(MUTED).text(label, x, sy + 28, { width: sw });
    doc.moveTo(x, sy + 64).lineTo(x + sw, sy + 64).stroke();
    doc.text('Date', x, sy + 68, { width: sw });
  });

  // ---- footers ----
  const range = doc.bufferedPageRange();
  for (let i = 0; i < range.count; i++) {
    doc.switchToPage(range.start + i);
    doc.page.margins.bottom = 0;  // the footer sits inside the bottom margin; without this, writing it would start a new blank page
    doc.font('Helvetica').fontSize(7.5).fillColor(MUTED).text(`SiteGuard   |   ${employee.name} (${employee.employeeId})   |   Page ${i + 1} of ${range.count}   |   Computer-generated from supervisor-confirmed records.`, M, doc.page.height - 30, { width: W, align: 'center', lineBreak: false });
  }
  return doc;
}


// ---- one violation notice: the exact fault and the pictures, on one page -------------------------------------------------------------------------
const FAULT_TEXT = {
  HELMET: 'No safety helmet was seen on this worker\'s head.',
  VEST: 'No high-visibility safety vest was seen on this worker\'s body.',
  BOOTS: 'No safety boots were seen on this worker\'s feet.',
  GLOVES: 'No safety gloves were seen on this worker\'s hands.',
  GOGGLES: 'No safety goggles were seen on this worker\'s eyes.',
};

// "NO HELMET, NO VEST" -> [{ item: 'HELMET', text: 'No safety helmet was seen...' }, ...]
export function faultLines(missing) {
  return String(missing || '').split(/\s*[,+]\s*/).filter(Boolean).map((part) => {
    const item = part.trim().toUpperCase().replace(/^NO\s+/, '');
    return { item, text: FAULT_TEXT[item] || (item === 'UNCLEAR' ? 'The camera could not judge this worker clearly. A supervisor must look at the picture.' : `${part.trim()}.`) };
  });
}

export function buildViolationNotice({ violation: v, employee, sectorName, penalty, policy, readUpload, preparedBy, now = new Date() }) {
  const doc = new PDFDocument({ size: 'A4', margin: M, bufferPages: true, info: { Title: `Violation notice ${String(v.number).padStart(5, '0')}`, Author: 'SiteGuard', Subject: 'PPE violation notice' } });
  const W = doc.page.width - 2 * M;
  const para = (text, opts = {}) => doc.font(opts.bold ? 'Helvetica-Bold' : 'Helvetica').fontSize(opts.size || 9.5).fillColor(opts.color || INK).text(text, M, doc.y, { width: W });
  const row = (label, value, color = INK) => {
    const y = doc.y;
    doc.font('Helvetica-Bold').fontSize(9).fillColor(MUTED).text(label, M, y, { width: 118 });
    doc.font('Helvetica').fontSize(9.5).fillColor(color).text(String(value || '-'), M + 122, y, { width: W - 122 });
    doc.y = Math.max(doc.y, y + 13);
  };
  const picture = (buf, x, y, w, h, caption) => {
    doc.rect(x, y, w, h).fillAndStroke(SOFT, LINE);
    if (buf) { try { doc.image(buf, x + 2, y + 2, { fit: [w - 4, h - 4], align: 'center', valign: 'center' }); } catch { doc.font('Helvetica').fontSize(8).fillColor(MUTED).text('Picture could not be shown', x, y + h / 2 - 4, { width: w, align: 'center' }); } }
    else doc.font('Helvetica').fontSize(8).fillColor(MUTED).text('No picture saved', x, y + h / 2 - 4, { width: w, align: 'center' });
    doc.font('Helvetica-Bold').fontSize(8).fillColor(MUTED).text(caption, x, y + h + 4, { width: w, align: 'center' });
  };
  const confirmed = ['Confirmed', 'Acknowledged', 'Disputed', 'Resolved'].includes(v.status);

  // title band
  doc.rect(0, 0, doc.page.width, 72).fill('#0f1b28');
  doc.font('Helvetica-Bold').fontSize(20).fillColor('#ffffff').text('Violation Notice', M, 18);
  doc.font('Helvetica').fontSize(9.5).fillColor('#b9c6d4').text('SiteGuard - PPE compliance', M, 44);
  doc.font('Helvetica-Bold').fontSize(11).fillColor('#ffc400').text(`Notice no. V-${String(v.number).padStart(5, '0')}`, M, 20, { width: W, align: 'right' });
  doc.font('Helvetica').fontSize(9).fillColor('#b9c6d4').text(`Prepared ${when(now)}`, M, 36, { width: W, align: 'right' });
  doc.text(`By ${preparedBy}`, M, 49, { width: W, align: 'right' });
  doc.y = 88;

  // the exact fault, large
  const faults = faultLines(v.missing);
  const boxH = 44 + faults.length * 18;
  const y0 = doc.y;
  doc.rect(M, y0, W, boxH).fillAndStroke('#fef3f2', BAD);
  doc.rect(M, y0, 6, boxH).fill(BAD);
  doc.font('Helvetica-Bold').fontSize(8.5).fillColor(BAD).text('THE EXACT FAULT', M + 16, y0 + 8);
  doc.font('Helvetica-Bold').fontSize(17).fillColor(BAD).text(plainMissing(v.missing), M + 16, y0 + 20, { width: W - 28 });
  let ly = y0 + 44;
  faults.forEach((f) => { doc.font('Helvetica').fontSize(10).fillColor(INK).text(`-  ${f.text}`, M + 16, ly, { width: W - 28 }); ly += 18; });
  doc.y = y0 + boxH + 12;

  // facts
  row('Employee', `${employee.name}  (${employee.employeeId})`);
  row('Work role', employee.jobRole || '-');
  row('Sector', sectorName || employee.department || '-');
  row('Date and time', when(v.occurredAt), INK);
  row('Place', v.location || 'Not recorded');
  row('How it was caught', SOURCE[v.source] || v.source || '-');
  if (v.catches > 1) row('Times caught that day', `${v.catches} (counted as one violation for the day)`);
  row('Status', STATUS_TEXT[v.status] || v.status, v.status === 'Disputed' ? WARN : confirmed ? INK : MUTED);
  row('Confirmed by', v.reviewedBy ? `${v.reviewedBy}, ${when(v.reviewedAt)}` : '-');
  const reply = (v.log || []).filter((l) => ['Acknowledged', 'Disputed'].includes(l.action)).pop();
  if (reply) row('Employee reply', `${reply.action}${reply.note ? `: "${reply.note}"` : ''}`);
  if (v.remarks) row('Remark', v.remarks);
  doc.moveDown(0.5);

  // the pictures
  const py = doc.y, pw = (W - 12) / 2, ph = 215;
  picture(readUpload(v.evidencePath), M, py, pw, ph, 'THE WORKER (close-up)');
  picture(readUpload(v.contextPath), M + pw + 12, py, pw, ph, 'THE WHOLE PICTURE where it was caught');
  doc.y = py + ph + 24;

  if (penalty) {
    row('Penalty', `${money(penalty.amount, penalty.currency || policy.currency)} - ${PENALTY_TEXT[penalty.status] || penalty.status}${penalty.decidedBy ? ` (${penalty.decidedBy})` : ''}`, penalty.status === 'Waived' ? OK : BAD);
    if (penalty.reason) row('Penalty reason', penalty.reason);
    doc.moveDown(0.3);
  }
  if (!confirmed) para('This is only an alert from the camera. It is NOT a violation, and carries no penalty, unless a supervisor confirms it.', { size: 9, color: WARN, bold: true });
  para('Your right to dispute: you may dispute this notice with a written reason, in the employee portal or to your supervisor. A disputed notice is looked at again by a supervisor before anything is collected.', { size: 8.5, color: MUTED });

  const range = doc.bufferedPageRange();
  for (let i = 0; i < range.count; i++) {
    doc.switchToPage(range.start + i);
    doc.page.margins.bottom = 0;
    doc.font('Helvetica').fontSize(7.5).fillColor(MUTED).text(`SiteGuard   |   Notice V-${String(v.number).padStart(5, '0')}   |   ${employee.name} (${employee.employeeId})   |   Computer-generated from the records.`, M, doc.page.height - 30, { width: W, align: 'center' });
  }
  return doc;
}
