// The SiteGuard API. One system of record for both websites.
//   Detector  -> POST /api/ingest/violations   (a violation arrives as "Pending review", with no name attached)
//   Supervisor-> reviews it, confirms it against a named employee (or dismisses it); penalties are proposed and need approval
//   Employee  -> sees only their own confirmed violations and penalties, and can acknowledge or dispute
import bcrypt from 'bcryptjs';
import cors from 'cors';
import crypto from 'node:crypto';
import express from 'express';
import fs from 'node:fs';
import jwt from 'jsonwebtoken';
import path from 'node:path';
import { COUNTED, newPenaltyBatches } from './policy.js';
import { dayKey, itemsOf, mergeItems } from './daily.js';
import { makeRemark } from './remarks.js';
import sharp from 'sharp';
import { EMPLOYEE_PASSWORD } from './defaults.js';
import { buildEmployeeReport, buildViolationNotice } from './report.js';
import { payslips } from './salary.js';

const wrap = (fn) => (req, res, next) => Promise.resolve(fn(req, res, next)).catch(next);
const now = () => new Date().toISOString();
// A face-match suggestion from the detector. It is only a hint for the supervisor and is never used as a decision.
const cleanSuggestion = (s) => (s && typeof s.employeeId === 'string' ? { employeeId: s.employeeId.slice(0, 20), name: String(s.name || '').slice(0, 80), jobRole: String(s.jobRole || '').slice(0, 60), department: String(s.department || '').slice(0, 60), score: Number(s.score) || 0, dummy: s.dummy === true } : null);
// A 3-letter supervisor code: the sector's first letter, then the next free pair of letters (BCE, BWE, ...), so codes never repeat.
export function nextCode(used, sectorName = '') {
  const first = (String(sectorName).replace(/[^A-Za-z]/g, '')[0] || 'S').toUpperCase();
  const A = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  for (const a of ['B', ...A]) for (const b of A) { const c = `${a}${first}${b}`; if (!used.has(c)) return c; }
  return `Z${first}Z`;
}
const publicUser = (u) => ({ id: u._id, employeeId: u.employeeId, name: u.name, role: u.role, department: u.department || '', jobRole: u.jobRole || '', photo: u.photo || '', sectorId: u.sectorId || null, isAdmin: u.isAdmin === true, code: u.code || '', field: u.field || '', className: u.className || '' });

// What a supervisor sees about a team member (includes pay, which the sign-in response and the detector never get).
const staff = (u) => ({ ...publicUser(u), monthlySalary: u.monthlySalary || 0 });

export function createApp({ db, policy, secret, ingestKey, uploadsDir, demoMode = false, origins = ['http://localhost:3001', 'http://localhost:3002', 'http://localhost:3003'] }) {
  const app = express();
  fs.mkdirSync(uploadsDir, { recursive: true });
  app.use(cors({ origin: origins }));
  app.use(express.json({ limit: '15mb' }));
  app.use('/uploads', express.static(uploadsDir));

  const notify = (n) => db.notifications.insertAsync({ at: now(), read: false, sectorId: null, ...n });
  const ITEMS = ['helmet', 'vest', 'goggles', 'gloves', 'boots'];
  // A non-admin supervisor only sees and decides on the cases of their own sector (kind of work).
  const scope = (req) => (req.user.isAdmin || !req.user.sectorId ? {} : { sectorId: req.user.sectorId });
  const inScope = (req, doc) => req.user.isAdmin || !req.user.sectorId || doc.sectorId === req.user.sectorId;
  const adminOnly = (req, res, next) => (req.user.isAdmin ? next() : res.status(403).json({ error: 'Only the head supervisor can do this.' }));
  const auth = (req, res, next) => {
    const header = req.headers.authorization || '';
    try {
      req.user = jwt.verify(header.startsWith('Bearer ') ? header.slice(7) : '', secret);
      next();
    } catch {
      res.status(401).json({ error: 'Please sign in.' });
    }
  };
  const only = (role) => (req, res, next) => (req.user.role === role ? next() : res.status(403).json({ error: 'This is not available to your role.' }));

  // Apply the penalty policy to one employee. Safe to call again: violations already attached are skipped.
  async function applyPolicy(employee) {
    const mine = await db.violations.findAsync({ employeeId: employee._id });
    const created = [];
    for (const batch of newPenaltyBatches(mine, policy)) {
      const reason = `${policy.proposeAt} violations within ${policy.windowDays} days: ` + batch.map((v) => `#${v.number} ${v.missing}`).join('; ');
      const penalty = await db.penalties.insertAsync({
        employeeId: employee._id, employeeName: employee.name, sectorId: batch[0].sectorId || null, status: 'Proposed', amount: policy.amount, currency: policy.currency,
        reason, violationIds: batch.map((v) => v._id), createdAt: now(), decidedBy: '', decidedAt: '', note: '',
      });
      await db.violations.updateAsync({ _id: { $in: batch.map((v) => v._id) } }, { $set: { penaltyId: penalty._id } }, { multi: true });
      await notify({ toRole: 'supervisor', message: `Penalty proposed for ${employee.name} (${employee.employeeId}): ${policy.proposeAt} violations. Please review.` });
      created.push(penalty);
    }
    return created;
  }

  // (Re)write the short remark of a case from its facts, unless a supervisor has edited it.
  async function refreshRemark(id) {
    const v = await db.violations.findOneAsync({ _id: id });
    if (!v || v.remarksEdited) return;
    const employee = v.employeeId ? await db.users.findOneAsync({ _id: v.employeeId })
      : v.suggested ? await db.users.findOneAsync({ employeeId: v.suggested.employeeId, role: 'employee' }) : null;
    const since = new Date(Date.now() - policy.windowDays * 86400000).toISOString();
    const earlier = employee ? (await db.violations.findAsync({ employeeId: employee._id, status: { $in: COUNTED }, occurredAt: { $gte: since } })).filter((x) => x._id !== v._id).length : 0;
    await db.violations.updateAsync({ _id: id }, { $set: { remarks: makeRemark({ v, employee, prior: earlier, proposeAt: policy.proposeAt }) } });
  }

  async function nextNumber() {
    const all = await db.violations.findAsync({});
    return all.reduce((m, v) => Math.max(m, v.number || 0), 0) + 1;
  }

  // One violation as a one-page notice: the exact fault, the employee, when and where, and the close-up and whole pictures.
  async function sendNotice(res, v, preparedBy) {
    const employee = v.employeeId ? await db.users.findOneAsync({ _id: v.employeeId }) : null;
    const who = employee || { name: v.suggested?.name || v.workerRef || 'Not yet identified', employeeId: v.suggested?.employeeId || '-', jobRole: v.suggested?.jobRole || '', department: v.suggested?.department || '' };
    const sector = (employee?.sectorId || v.sectorId) ? await db.sectors.findOneAsync({ _id: employee?.sectorId || v.sectorId }) : null;
    const penalty = v.penaltyId ? await db.penalties.findOneAsync({ _id: v.penaltyId }) : null;
    const pictures = new Map();
    for (const p of [v.evidencePath, v.contextPath].filter((q) => q && String(q).startsWith('/uploads/'))) {
      try { pictures.set(p, await sharp(fs.readFileSync(path.join(uploadsDir, path.basename(p)))).rotate().resize({ width: 1000, withoutEnlargement: true }).jpeg({ quality: 80 }).toBuffer()); } catch { /* a missing picture is left blank */ }
    }
    const doc = buildViolationNotice({ violation: v, employee: who, sectorName: sector?.name || '', penalty, policy, readUpload: (p) => pictures.get(p) || null, preparedBy });
    res.setHeader('content-type', 'application/pdf');
    res.setHeader('content-disposition', `attachment; filename="violation-notice-${String(v.number).padStart(5, '0')}.pdf"`);
    doc.pipe(res);
    doc.end();
  }

  // The complaint report of one employee as a PDF: details and photo, confirmed violations with their pictures, fines, and what is still only an alert.
  async function sendReport(res, employee, preparedBy) {
    const sector = employee.sectorId ? await db.sectors.findOneAsync({ _id: employee.sectorId }) : null;
    const boss = employee.sectorId ? (await db.users.findOneAsync({ role: 'supervisor', isAdmin: false, sectorId: employee.sectorId })) || (await db.users.findOneAsync({ role: 'supervisor', sectorId: employee.sectorId })) : null;
    const cases = await db.violations.findAsync({ $or: [{ employeeId: employee._id }, { employeeId: null, 'suggested.employeeId': employee.employeeId }] }).sort({ occurredAt: -1 });
    const penalties = await db.penalties.findAsync({ employeeId: employee._id }).sort({ createdAt: -1 });
    // Pictures are shrunk to a sensible size for paper (900 px wide, good JPEG), so a report with many pictures stays a few hundred KB, not megabytes.
    const pictures = new Map();
    for (const p of new Set(cases.flatMap((v) => [v.evidencePath, v.contextPath]).filter((p) => p && String(p).startsWith('/uploads/')))) {
      try { pictures.set(p, await sharp(fs.readFileSync(path.join(uploadsDir, path.basename(p)))).rotate().resize({ width: 900, withoutEnlargement: true }).jpeg({ quality: 78 }).toBuffer()); } catch { /* a missing or unreadable picture is shown as "no picture saved" */ }
    }
    const readUpload = (p) => pictures.get(p) || null;
    const doc = buildEmployeeReport({
      employee: { name: employee.name, employeeId: employee.employeeId, jobRole: employee.jobRole, field: employee.field, className: employee.className, photo: employee.photo, sectorName: sector?.name || employee.department || '', supervisorName: boss?.name || '' },
      violations: cases.filter((v) => v.employeeId && COUNTED.includes(v.status)),
      pending: cases.filter((v) => v.status === 'Pending review'),
      dismissedCount: cases.filter((v) => v.status === 'Dismissed').length,
      penalties, policy, readUpload, preparedBy,
    });
    res.setHeader('content-type', 'application/pdf');
    res.setHeader('content-disposition', `attachment; filename="complaint-report-${employee.employeeId}.pdf"`);
    doc.pipe(res);
    doc.end();
  }

  app.get('/api/health', (req, res) => res.json({ ok: true, time: now() }));

  // ---- sign in -------------------------------------------------------------------------------
  app.post('/api/auth/login', wrap(async (req, res) => {
    const { employeeId, password } = req.body || {};
    const user = employeeId ? await db.users.findOneAsync({ employeeId: String(employeeId).trim().toUpperCase() }) : null;
    if (!user || !(await bcrypt.compare(String(password || ''), user.passwordHash))) return res.status(401).json({ error: 'Wrong ID or password.' });
    if (user.pending) return res.status(403).json({ error: "This account is waiting for the head supervisor's approval." });
    const token = jwt.sign({ id: user._id, employeeId: user.employeeId, name: user.name, role: user.role, sectorId: user.sectorId || null, isAdmin: user.isAdmin === true }, secret, { expiresIn: '8h' });
    const sector = user.sectorId ? await db.sectors.findOneAsync({ _id: user.sectorId }) : null;
    res.json({ token, user: { ...publicUser(user), sectorName: sector?.name || '' } });
  }));

  // A new supervisor creates their own account on the sign-in page. It comes with a NEW, empty sector of their own (their site and its required
  // gear), so they see only what they add themselves: never another sector's cases, employees, photos or pay.
  const signupsSeen = new Map();
  app.post('/api/auth/signup', wrap(async (req, res) => {
    const ip = req.ip || '';
    if ((signupsSeen.get(ip) || 0) >= 5) return res.status(429).json({ error: 'Too many accounts were created from here. Ask the head supervisor.' });
    const name = String(req.body?.name || '').trim().slice(0, 80);
    const password = String(req.body?.password || '');
    if (!name) return res.status(400).json({ error: 'Enter your name.' });
    if (password.length < 6) return res.status(400).json({ error: 'A password needs at least 6 characters.' });
    const { value, error } = cleanSector({ name: req.body?.siteName, requiredItems: req.body?.requiredItems, conditionClass: req.body?.conditionClass, location: req.body?.location || req.body?.siteName, fields: req.body?.fields, classes: req.body?.classes });
    if (error) return res.status(400).json({ error: error.replace('the sector a name, for example Civil Construction Site', 'your site or kind of work a name, for example Electrical Wiring Works') });
    if (await db.sectors.findOneAsync({ name: value.name })) return res.status(409).json({ error: 'A site or sector with that name already exists. Choose another name.' });
    if ((await db.sectors.countAsync({ selfMade: true })) >= 50) return res.status(429).json({ error: 'No more accounts can be created here. Ask the head supervisor.' });
    signupsSeen.set(ip, (signupsSeen.get(ip) || 0) + 1);
    const sector = await db.sectors.insertAsync({ ...value, createdAt: now(), createdBy: name, selfMade: true });
    const all = await db.users.findAsync({ role: 'supervisor' });
    const employeeId = `S${String(Math.max(0, ...all.map((u) => Number(String(u.employeeId).replace(/\D/g, '')) || 0)) + 1).padStart(3, '0')}`;
    const code = nextCode(new Set(all.map((u) => u.code).filter(Boolean)), sector.name);
    await db.users.insertAsync({ employeeId, name, role: 'supervisor', sectorId: sector._id, isAdmin: false, jobRole: 'Supervisor', department: sector.name, code, passwordHash: await bcrypt.hash(password, 10) });
    await notify({ toRole: 'supervisor', sectorId: null, message: `${name} created a supervisor account with a new sector, ${sector.name}.` });
    res.status(201).json({ employeeId, code, sectorName: sector.name });
  }));

  // ---- from the detector ---------------------------------------------------------------------
  app.post('/api/ingest/violations', wrap(async (req, res) => {
    if (!ingestKey || req.headers['x-ingest-key'] !== ingestKey) return res.status(401).json({ error: 'Bad ingest key.' });
    const items = Array.isArray(req.body?.items) ? req.body.items.slice(0, 50) : [];
    if (!items.length) return res.status(400).json({ error: 'No items.' });
    const ids = [];
    const stats = { created: 0, repeats: 0 };
    let number = await nextNumber();
    const offset = policy.timezoneOffsetMinutes ?? 330;
    const batchStart = now(); // unnamed catches are only matched against earlier requests: two people in one picture are two people
    for (const item of items) {
      const occurredAt = item.occurredAt || now();
      const day = dayKey(occurredAt, offset);
      const suggested = cleanSuggestion(item.suggested);
      const missing = itemsOf(item.missing).join(', ') || 'UNKNOWN';
      const sector = item.sector ? await db.sectors.findOneAsync({ _id: String(item.sector) }) : null;
      const sectorId = sector ? sector._id : null;
      const employee = suggested ? await db.users.findOneAsync({ employeeId: suggested.employeeId, role: 'employee' }) : null;

      // One violation per person per day: a person caught again the same day is a repeat catch on that day's case.
      let existing = null;
      if (employee) {
        existing = await db.violations.findOneAsync({ dayKey: day, $or: [{ employeeId: employee._id }, { 'suggested.employeeId': suggested.employeeId }] });
      } else {
        // Nobody identified: the same place, the same items, still waiting for review, in the last 10 minutes is the same catch.
        existing = await db.violations.findOneAsync({ dayKey: day, suggested: null, employeeId: null, sectorId, status: 'Pending review', location: item.location || '', missing, recordedAt: { $gte: new Date(Date.now() - 600000).toISOString(), $lt: batchStart } });
      }
      if (existing) {
        await db.violations.updateAsync({ _id: existing._id }, {
          $set: { catches: (existing.catches || 1) + 1, lastCaughtAt: occurredAt, missing: mergeItems(existing.missing, missing) },
          $push: { log: { at: now(), by: 'Detector', action: 'Caught again', note: `${missing}${item.location ? ` at ${item.location}` : ''}` } },
        });
        await refreshRemark(existing._id);
        ids.push(existing._id);
        stats.repeats += 1;
        continue;
      }

      const saveJpeg = (data) => {
        const file = `${crypto.randomUUID()}.jpg`;
        fs.writeFileSync(path.join(uploadsDir, file), Buffer.from(String(data).replace(/^data:[^,]+,/, ''), 'base64'));
        return `/uploads/${file}`;
      };
      let evidencePath = item.evidencePath || '';
      if (item.evidenceBase64) evidencePath = saveJpeg(item.evidenceBase64); // a close-up of the worker
      const contextPath = item.contextBase64 ? saveJpeg(item.contextBase64) : ''; // the whole picture
      const doc = await db.violations.insertAsync({
        number: number++, sectorId, sectorName: sector?.name || '', status: 'Pending review', employeeId: null, employeeName: '', workerRef: item.workerRef || 'Worker', missing, dayKey: day, catches: 1, lastCaughtAt: occurredAt,
        reason: item.reason || '', location: item.location || '', source: item.source || 'detector', sourceName: item.sourceName || '',
        occurredAt, recordedAt: now(), evidencePath, contextPath, suggested, reviewedBy: '', reviewedAt: '', reviewNote: '', penaltyId: null, log: [{ at: now(), by: 'Detector', action: 'Detected', note: '' }],
      });
      await refreshRemark(doc._id);
      ids.push(doc._id);
      stats.created += 1;
      // The employee hears straight away. This is an alert, not a violation: a supervisor still has to confirm it.
      if (employee) await notify({ toUserId: employee._id, message: `Safety alert: you were seen without ${missing.toLowerCase().replace(/no /g, '')}${item.location ? ` at ${item.location}` : ''}. A supervisor will review it.` });
    }
    if (stats.created) await notify({ toRole: 'supervisor', sectorId: (await db.violations.findOneAsync({ _id: ids[ids.length - 1] }))?.sectorId || null, message: `${stats.created} new case(s) waiting for your review.` });
    res.status(201).json({ ...stats, ids });
  }));

  // A worker-down alert from the detector: a worker fell or stopped moving. This is an ALERT for a supervisor to go and check, not a finding of cause.
  app.post('/api/ingest/accidents', wrap(async (req, res) => {
    if (!ingestKey || req.headers['x-ingest-key'] !== ingestKey) return res.status(401).json({ error: 'Bad ingest key.' });
    const b = req.body || {};
    const sector = b.sector ? await db.sectors.findOneAsync({ _id: String(b.sector) }) : null;
    const suggested = cleanSuggestion(b.suggested);
    const employee = suggested ? await db.users.findOneAsync({ employeeId: suggested.employeeId, role: 'employee' }) : null;
    const occurredAt = b.occurredAt || now();
    // The same footage can raise the same alert twice; one alert per place, footage and minute is enough.
    const dup = await db.accidents.findOneAsync({ sectorId: sector?._id || null, location: String(b.location || ''), occurredMinute: String(occurredAt).slice(0, 16), sourceName: String(b.sourceName || '') });
    if (dup) return res.status(200).json({ id: dup._id, duplicate: true });
    const saveJpeg = (data) => { const file = `${crypto.randomUUID()}.jpg`; fs.writeFileSync(path.join(uploadsDir, file), Buffer.from(String(data).replace(/^data:[^,]+,/, ''), 'base64')); return `/uploads/${file}`; };
    const all = await db.accidents.findAsync({});
    const number = all.reduce((m, a) => Math.max(m, a.number || 0), 0) + 1;
    const venue = [sector?.name, b.location].filter(Boolean).join(' · ') || 'the site';
    const doc = await db.accidents.insertAsync({
      number, sectorId: sector?._id || null, sectorName: sector?.name || '', location: String(b.location || '').slice(0, 80), venue, kind: String(b.kind || 'WORKER DOWN').slice(0, 40),
      detail: String(b.detail || '').slice(0, 300), status: 'Open', occurredAt, occurredMinute: String(occurredAt).slice(0, 16), recordedAt: now(), source: b.source || 'detector', sourceName: String(b.sourceName || '').slice(0, 120),
      employeeId: employee?._id || null, employeeCode: employee?.employeeId || suggested?.employeeId || '', employeeName: employee?.name || suggested?.name || '',
      evidencePath: b.evidenceBase64 ? saveJpeg(b.evidenceBase64) : '', contextPath: b.contextBase64 ? saveJpeg(b.contextBase64) : '', log: [{ at: now(), by: 'Detector', action: 'Raised', note: '' }],
    });
    await notify({ toRole: 'supervisor', sectorId: doc.sectorId, accident: true, message: doc.kind === 'WORKER DOWN' ? `ACCIDENT ALERT: a worker is down at ${venue}${doc.employeeName ? ` (${doc.employeeName})` : ''}. Go and check now.` : `ACCIDENT ALERT: ${doc.kind.toLowerCase()} at ${venue}. Go and check now.` });
    if (employee) await notify({ toUserId: employee._id, message: `An accident alert was raised for you at ${venue}. Help is being sent.` });
    res.status(201).json({ id: doc._id });
  }));

  app.get('/api/sectors/public', wrap(async (req, res) => {
    const sectors = await db.sectors.findAsync({}).sort({ name: 1 });
    const sups = await db.users.findAsync({ role: 'supervisor' });
    res.json(sectors.map((s) => ({ id: s._id, name: s.name, conditionClass: s.conditionClass, requiredItems: s.requiredItems, location: s.location, fields: s.fields || [], classes: s.classes || [], supervisors: sups.filter((u) => u.sectorId === s._id && !u.pending).map((u) => u.name) })));
  }));

  // Demo only: the list of dummy employees, so the employee site can switch between them without a login page.
  if (demoMode) app.get('/api/demo/employees', wrap(async (req, res) => res.json((await db.users.findAsync({ role: 'employee' }).sort({ employeeId: 1 })).map((u) => ({ employeeId: u.employeeId, name: u.name, jobRole: u.jobRole || '' })))));

  // ---- supervisor ----------------------------------------------------------------------------
  // Each route carries its own sign-in and role check (a shared router-level check would also catch the other role's routes).
  const guarded = (role) => ({
    get: (p, h) => app.get(`/api${p}`, auth, only(role), h),
    post: (p, h) => app.post(`/api${p}`, auth, only(role), h),
  });
  const sup = guarded('supervisor');

  sup.get('/review/queue', wrap(async (req, res) => res.json(await db.violations.findAsync({ status: 'Pending review', ...scope(req) }).sort({ number: -1 }))));

  sup.post('/violations/:id/decision', wrap(async (req, res) => {
    const v = await db.violations.findOneAsync({ _id: req.params.id });
    if (!v) return res.status(404).json({ error: 'No such violation.' });
    if (!inScope(req, v)) return res.status(403).json({ error: 'This case belongs to another sector.' });
    if (v.status !== 'Pending review') return res.status(409).json({ error: 'This one has already been reviewed.' });
    const { decision, employeeId, note = '' } = req.body || {};
    if (decision === 'dismiss') {
      await db.violations.updateAsync({ _id: v._id }, { $set: { status: 'Dismissed', reviewedBy: req.user.name, reviewedAt: now(), reviewNote: note }, $push: { log: { at: now(), by: req.user.name, action: 'Dismissed', note } } });
      return res.json({ status: 'Dismissed' });
    }
    if (decision !== 'confirm') return res.status(400).json({ error: "Decision must be 'confirm' or 'dismiss'." });
    const employee = employeeId ? await db.users.findOneAsync({ _id: employeeId, role: 'employee' }) : null;
    if (!employee) return res.status(400).json({ error: 'Choose which employee this violation belongs to.' });
    await db.violations.updateAsync({ _id: v._id }, { $set: { status: 'Confirmed', employeeId: employee._id, employeeName: employee.name, reviewedBy: req.user.name, reviewedAt: now(), reviewNote: note },
      $push: { log: { at: now(), by: req.user.name, action: `Confirmed against ${employee.name}`, note } } });
    await refreshRemark(v._id);
    await notify({ toUserId: employee._id, message: `A violation (${v.missing}) was recorded against you. You can view it and respond.` });
    const penalties = await applyPolicy(employee);
    res.json({ status: 'Confirmed', penaltiesProposed: penalties.length });
  }));

  sup.post('/violations/:id/remarks', wrap(async (req, res) => {
    const remarks = String(req.body?.remarks || '').trim().slice(0, 600);
    const target = await db.violations.findOneAsync({ _id: req.params.id });
    if (!target || !inScope(req, target)) return res.status(403).json({ error: 'This case belongs to another sector.' });
    const n = await db.violations.updateAsync({ _id: req.params.id }, { $set: { remarks, remarksEdited: true } });
    res.json({ updated: n });
  }));

  sup.get('/violations', wrap(async (req, res) => {
    const q = { ...(req.query.status ? { status: req.query.status } : { status: { $ne: 'Pending review' } }), ...scope(req) };
    res.json(await db.violations.findAsync(q).sort({ number: -1 }));
  }));

  sup.get('/penalties', wrap(async (req, res) => res.json(await db.penalties.findAsync({ ...(req.query.status ? { status: req.query.status } : {}), ...scope(req) }).sort({ createdAt: -1 }))));

  // A supervisor puts a penalty on an employee, by employee ID, who has confirmed violations that no penalty covers yet. It is issued at once: the
  // supervisor's decision is the approval. The employee is told and can dispute it like any other penalty.
  sup.post('/penalties', wrap(async (req, res) => {
    const code = String(req.body?.employeeId || '').trim().toUpperCase();
    const employee = code ? await db.users.findOneAsync({ role: 'employee', employeeId: code }) : null;
    if (!employee || !inScope(req, employee)) return res.status(404).json({ error: 'No employee with that ID in your sector.' });
    const open = (await db.violations.findAsync({ employeeId: employee._id })).filter((v) => COUNTED.includes(v.status) && !v.penaltyId);
    if (!open.length) return res.status(400).json({ error: `${employee.name} (${code}) has no confirmed violation without a penalty, so there is nothing to base a penalty on.` });
    const wanted = Array.isArray(req.body?.violationIds) && req.body.violationIds.length ? req.body.violationIds.map(String) : open.map((v) => v._id);
    const chosen = open.filter((v) => wanted.includes(v._id));
    if (!chosen.length || chosen.length !== wanted.length) return res.status(400).json({ error: 'One of the chosen violations is not an open, confirmed violation of this employee.' });
    const amount = Number(req.body?.amount ?? policy.amount);
    if (!Number.isFinite(amount) || amount <= 0 || amount > 100000) return res.status(400).json({ error: 'Enter an amount above 0 and up to 100000.' });
    const reason = String(req.body?.reason || '').trim().slice(0, 300) || `Put by ${req.user.name}: ` + chosen.map((v) => `#${v.number} ${v.missing}`).join('; ');
    const penalty = await db.penalties.insertAsync({
      employeeId: employee._id, employeeName: employee.name, sectorId: chosen[0].sectorId || employee.sectorId || null, status: 'Issued', amount: Math.round(amount * 100) / 100,
      currency: policy.currency, reason, violationIds: chosen.map((v) => v._id), createdAt: now(), decidedBy: req.user.name, decidedAt: now(), note: 'Put by a supervisor', manual: true,
    });
    await db.violations.updateAsync({ _id: { $in: chosen.map((v) => v._id) } }, { $set: { penaltyId: penalty._id } }, { multi: true });
    await notify({ toUserId: employee._id, message: `A penalty of ${penalty.currency} ${penalty.amount} has been issued to you. You can view it and dispute it.` });
    res.status(201).json(penalty);
  }));
  sup.post('/penalties/:id/decide', wrap(async (req, res) => {
    const p = await db.penalties.findOneAsync({ _id: req.params.id });
    if (!p) return res.status(404).json({ error: 'No such penalty.' });
    const { decision, note = '' } = req.body || {};
    const allowed = { Proposed: ['Issued', 'Waived'], Disputed: ['Issued', 'Waived'], Issued: ['Paid', 'Waived'] }[p.status] || [];
    if (!allowed.includes(decision)) return res.status(400).json({ error: `A penalty that is ${p.status} can be set to: ${allowed.join(', ') || 'nothing'}.` });
    await db.penalties.updateAsync({ _id: p._id }, { $set: { status: decision, decidedBy: req.user.name, decidedAt: now(), note } });
    if (decision === 'Issued') await notify({ toUserId: p.employeeId, message: `A penalty of ${p.currency} ${p.amount} has been issued to you. You can view it and dispute it.` });
    res.json({ status: decision });
  }));

  // ---- sectors and supervisors: the head supervisor sets up kinds of work and who supervises them ----
  const cleanSector = (b) => {
    const name = String(b?.name || '').trim().slice(0, 60);
    const items = [...new Set((Array.isArray(b?.requiredItems) ? b.requiredItems : []).filter((i) => ITEMS.includes(i)))];
    if (!name) return { error: 'Give the sector a name, for example Civil Construction Site.' };
    if (!items.length) return { error: 'Choose at least one item that must be worn.' };
    return { value: { name, conditionClass: String(b?.conditionClass || '').trim().slice(0, 80), requiredItems: items, location: String(b?.location || '').trim().slice(0, 80), ...cleanOptions(b) } };
  };
  // The sector's fields (areas of the site, such as Block A) and classes (conditions classes). The supervisor of the sector keeps these lists.
  const cleanList = (v) => [...new Set((Array.isArray(v) ? v : String(v || '').split(/[,\n]/)).map((x) => String(x).trim().slice(0, 60)).filter(Boolean))].slice(0, 12);
  // Only the lists that were actually sent are changed, so editing the required gear never wipes the fields and classes.
  const cleanOptions = (b) => ({ ...(b?.fields === undefined ? {} : { fields: cleanList(b.fields) }), ...(b?.classes === undefined ? {} : { classes: cleanList(b.classes) }) });
  sup.get('/sectors', wrap(async (req, res) => {
    const sups = await db.users.findAsync({ role: 'supervisor' });
    const cases = await db.violations.findAsync({});
    res.json((await db.sectors.findAsync({}).sort({ name: 1 })).filter((s) => req.user.isAdmin || !req.user.sectorId || s._id === req.user.sectorId).map((s) => ({ ...s, id: s._id, supervisors: sups.filter((u) => u.sectorId === s._id && !u.pending).map(publicUser), cases: cases.filter((c) => c.sectorId === s._id).length })));
  }));
  app.post('/api/sectors', auth, only('supervisor'), adminOnly, wrap(async (req, res) => {
    const { value, error } = cleanSector(req.body);
    if (error) return res.status(400).json({ error });
    if (await db.sectors.findOneAsync({ name: value.name })) return res.status(409).json({ error: 'A sector with that name already exists.' });
    const s = await db.sectors.insertAsync({ ...value, createdAt: now(), createdBy: req.user.name });
    res.status(201).json({ ...s, id: s._id });
  }));
  app.post('/api/sectors/:id', auth, only('supervisor'), wrap(async (req, res) => {
    if (!req.user.isAdmin && req.user.sectorId !== req.params.id) return res.status(403).json({ error: 'You can only change your own sector.' });
    const { value, error } = cleanSector(req.body);
    if (error) return res.status(400).json({ error });
    const n = await db.sectors.updateAsync({ _id: req.params.id }, { $set: value });
    res.json({ updated: n });
  }));
  // The supervisor of a sector (or the head supervisor) adds and removes the sector's fields and classes in the panel.
  sup.post('/sectors/:id/options', wrap(async (req, res) => {
    if (!req.user.isAdmin && req.user.sectorId !== req.params.id) return res.status(403).json({ error: 'You can only change your own sector.' });
    const options = cleanOptions(req.body);
    const n = await db.sectors.updateAsync({ _id: req.params.id }, { $set: options });
    res.json({ updated: n, ...options });
  }));
  sup.get('/supervisors', wrap(async (req, res) => {
    const sectors = Object.fromEntries((await db.sectors.findAsync({})).map((s) => [s._id, s.name]));
    res.json((await db.users.findAsync({ role: 'supervisor' }).sort({ employeeId: 1 })).filter((u) => req.user.isAdmin || !req.user.sectorId || u.sectorId === req.user.sectorId).map((u) => ({ ...publicUser(u), sectorName: sectors[u.sectorId] || '', pending: u.pending === true, requestedAt: u.requestedAt || '' })));
  }));
  app.post('/api/supervisors/:id/approve', auth, only('supervisor'), adminOnly, wrap(async (req, res) => {
    const n = await db.users.updateAsync({ _id: req.params.id, role: 'supervisor', pending: true }, { $set: { pending: false, approvedBy: req.user.name, approvedAt: now() } });
    res.json({ approved: n });
  }));
  app.post('/api/supervisors/:id/reject', auth, only('supervisor'), adminOnly, wrap(async (req, res) => {
    const n = await db.users.removeAsync({ _id: req.params.id, role: 'supervisor', pending: true }, {});
    res.json({ rejected: n });
  }));
  // Creates a supervisor account for a sector. The code is the next free S-number; the password is the code followed by @123 unless one is given.
  app.post('/api/supervisors', auth, only('supervisor'), adminOnly, wrap(async (req, res) => {
    const name = String(req.body?.name || '').trim().slice(0, 80);
    const sector = await db.sectors.findOneAsync({ _id: String(req.body?.sectorId || '') });
    if (!name) return res.status(400).json({ error: 'Enter the supervisor\'s name.' });
    if (!sector) return res.status(400).json({ error: 'Choose the sector this supervisor will look after.' });
    const taken = (await db.users.findAsync({ role: 'supervisor' })).map((u) => Number(String(u.employeeId).replace(/\D/g, '')) || 0);
    const employeeId = `S${String(Math.max(0, ...taken) + 1).padStart(3, '0')}`;
    const used = new Set((await db.users.findAsync({ role: 'supervisor' })).map((u) => u.code).filter(Boolean));
    let code = String(req.body?.code || '').trim().toUpperCase();
    if (code && !/^[A-Z]{3}$/.test(code)) return res.status(400).json({ error: 'The supervisor code is 3 letters, for example BCE.' });
    if (code && used.has(code)) return res.status(409).json({ error: `The code ${code} is already used by another supervisor.` });
    if (!code) code = nextCode(used, sector.name);
    const password = String(req.body?.password || '').trim() || `${employeeId}@123`;
    if (password.length < 6) return res.status(400).json({ error: 'A password needs at least 6 characters.' });
    const u = await db.users.insertAsync({ employeeId, name, role: 'supervisor', sectorId: sector._id, isAdmin: false, jobRole: 'Supervisor', department: sector.name, code, passwordHash: await bcrypt.hash(password, 10) });
    res.status(201).json({ ...publicUser(u), sectorName: sector.name, password });
  }));

  // ---- accidents: worker-down alerts, with a report a supervisor can acknowledge and close ----
  sup.get('/accidents', wrap(async (req, res) => res.json(await db.accidents.findAsync({ ...(req.query.status ? { status: req.query.status } : {}), ...scope(req) }).sort({ number: -1 }))));
  sup.post('/accidents/:id/status', wrap(async (req, res) => {
    const a = await db.accidents.findOneAsync({ _id: req.params.id });
    if (!a || !inScope(req, a)) return res.status(404).json({ error: 'No such accident report.' });
    const status = String(req.body?.status || '');
    if (!['Acknowledged', 'Resolved', 'False alarm'].includes(status)) return res.status(400).json({ error: 'Status must be Acknowledged, Resolved or False alarm.' });
    const note = String(req.body?.note || '').slice(0, 300);
    await db.accidents.updateAsync({ _id: a._id }, { $set: { status, closedBy: req.user.name, closedAt: now() }, $push: { log: { at: now(), by: req.user.name, action: status, note } } });
    res.json({ status });
  }));

  // The log: every catch, one row each, with the person's ID and name, what was missing, the picture, and the date and time. Accidents are in it too.
  sup.get('/log', wrap(async (req, res) => {
    const cases = await db.violations.findAsync({ ...scope(req) });
    const accidents = await db.accidents.findAsync({ ...scope(req) });
    const ids = Object.fromEntries((await db.users.findAsync({ role: 'employee' })).map((u) => [u._id, u.employeeId]));
    const rows = [
      ...cases.map((v) => ({ key: v._id, kind: 'Violation', number: v.number, userId: (v.employeeId && ids[v.employeeId]) || v.suggested?.employeeId || '', name: v.employeeName || v.suggested?.name || v.workerRef || '', violation: v.missing, status: v.status, sector: v.sectorName || '', location: v.location || '', image: v.evidencePath || '', at: v.occurredAt, catches: v.catches || 1, source: v.source || '' })),
      ...accidents.map((a) => ({ key: a._id, kind: 'Accident', number: a.number, userId: a.employeeCode || '', name: a.employeeName || 'Not identified', violation: `${a.kind}: accident alert`, status: a.status, sector: a.sectorName || '', location: a.location || '', image: a.evidencePath || '', at: a.occurredAt, catches: 1, source: a.source || '' })),
    ];
    res.json(rows.sort((a, b) => new Date(b.at) - new Date(a.at)));
  }));

  // The rules in force: the required gear of each sector, and the penalty policy.
  sup.get('/rules', wrap(async (req, res) => {
    const sectors = (await db.sectors.findAsync({})).filter((s) => req.user.isAdmin || !req.user.sectorId || s._id === req.user.sectorId).sort((a, b) => a.name.localeCompare(b.name));
    const counted = (await db.violations.findAsync({ ...scope(req) })).filter((v) => COUNTED.includes(v.status));
    res.json({ policy: { proposeAt: policy.proposeAt, windowDays: policy.windowDays, amount: policy.amount, currency: policy.currency },
      sectors: sectors.map((s) => ({ id: s._id, name: s.name, conditionClass: s.conditionClass, requiredItems: s.requiredItems, fields: s.fields || [], classes: s.classes || [], violated: counted.filter((v) => v.sectorId === s._id).length })) });
  }));

  // A supervisor sees the employees of their own sector; the head supervisor sees everyone.
  sup.get('/employees', wrap(async (req, res) => res.json((await db.users.findAsync({ role: 'employee', ...scope(req) }).sort({ name: 1 })).map(staff))));

  sup.get('/violations/:id/notice.pdf', wrap(async (req, res) => {
    const v = await db.violations.findOneAsync({ _id: req.params.id });
    if (!v || !inScope(req, v)) return res.status(404).json({ error: 'No such case.' });
    await sendNotice(res, v, `${req.user.name} (supervisor)`);
  }));

  sup.get('/employees/:id/report.pdf', wrap(async (req, res) => {
    const u = await db.users.findOneAsync({ _id: req.params.id, role: 'employee' });
    if (!u || !inScope(req, u)) return res.status(404).json({ error: 'No such employee.' });
    await sendReport(res, u, `${req.user.name} (supervisor)`);
  }));

  sup.get('/employees/:id/profile', wrap(async (req, res) => {
    const u = await db.users.findOneAsync({ _id: req.params.id, role: 'employee' });
    if (!u || !inScope(req, u)) return res.status(404).json({ error: 'No such employee.' });
    const violations = await db.violations.findAsync({ $or: [{ employeeId: u._id }, { employeeId: null, 'suggested.employeeId': u.employeeId }] }).sort({ number: -1 });
    const penalties = await db.penalties.findAsync({ employeeId: u._id }).sort({ createdAt: -1 });
    res.json({ employee: staff(u), violations, penalties, payslips: payslips(u.monthlySalary, penalties), currency: policy.currency });
  }));

  sup.post('/employees/:id/salary', wrap(async (req, res) => {
    const amount = Number(req.body?.monthlySalary);
    if (!Number.isFinite(amount) || amount < 0 || amount > 10000000) return res.status(400).json({ error: 'Enter a monthly salary between 0 and 10,000,000.' });
    const n = await db.users.updateAsync({ _id: req.params.id, role: 'employee' }, { $set: { monthlySalary: Math.round(amount) } });
    res.json({ updated: n });
  }));

  // A small profile photo (the browser shrinks it first). Kept with the employee record; replace or clear it any time.
  sup.post('/employees/:id/photo', wrap(async (req, res) => {
    const photo = String(req.body?.photo || '');
    if (photo && (!/^data:image\/(jpeg|png|webp);base64,/.test(photo) || photo.length > 300000)) return res.status(400).json({ error: 'Use a JPEG, PNG or WebP photo (it is shrunk automatically).' });
    const n = await db.users.updateAsync({ _id: req.params.id, role: 'employee' }, { $set: { photo } });
    res.json({ updated: n });
  }));

  sup.post('/employees', wrap(async (req, res) => {
    const { employeeId, name, department = '', jobRole = '', monthlySalary = 0, photo = '', field = '', className = '' } = req.body || {};
    if (!name || !String(name).trim()) return res.status(400).json({ error: "Enter the employee's name." });
    if (photo && (!/^data:image\/(jpeg|png|webp);base64,/.test(photo) || photo.length > 300000)) return res.status(400).json({ error: 'Use a JPEG, PNG or WebP photo (it is shrunk automatically).' });
    // The employee belongs to the sector of the supervisor who adds them (the head supervisor chooses a sector).
    const sectorId = req.user.isAdmin ? String(req.body?.sectorId || req.user.sectorId || '') : req.user.sectorId;
    const sector = sectorId ? await db.sectors.findOneAsync({ _id: sectorId }) : null;
    let id;
    let code = '';
    if (employeeId) {  // an explicit ID (the older form)
      id = String(employeeId).trim().toUpperCase();
    } else {
      // ID = the sector supervisor's 3-letter code + a number, for example BCE123. The number can be typed or is the next free one from 101.
      const boss = sector ? await db.users.findOneAsync({ role: 'supervisor', sectorId: sector._id, code: { $exists: true } }) : null;
      code = (req.user.isAdmin ? boss?.code : req.user.code) || boss?.code || '';
      if (!code) return res.status(400).json({ error: 'This sector has no supervisor code yet. Create its supervisor first.' });
      const mine = (await db.users.findAsync({ role: 'employee' })).map((u) => u.employeeId).filter((x) => x.startsWith(code)).map((x) => Number(x.slice(code.length)) || 0);
      const typed = Number(String(req.body?.number || '').replace(/\D/g, ''));
      id = `${code}${typed ? String(typed).padStart(3, '0') : String(Math.max(100, ...mine) + 1).padStart(3, '0')}`;
    }
    if (await db.users.findOneAsync({ employeeId: id })) return res.status(409).json({ error: `The ID ${id} already exists.` });
    const password = EMPLOYEE_PASSWORD; // every employee uses the same password, whatever is sent
    if (sector && field && !(sector.fields || []).includes(field)) return res.status(400).json({ error: "Choose one of the sector's fields." });
    const user = await db.users.insertAsync({ employeeId: id, name: String(name).trim().slice(0, 80), department: department || sector?.name || '', jobRole: String(jobRole).trim().slice(0, 60), monthlySalary: Math.max(0, Math.round(Number(monthlySalary) || 0)), role: 'employee', sectorId: sector?._id || null, field, className: String(className).slice(0, 60), photo, code, createdBy: req.user.name, passwordHash: await bcrypt.hash(password, 10) });
    res.status(201).json({ ...staff(user), password, passwordIsDefault: true });
  }));

  sup.get('/stats', wrap(async (req, res) => {
    const all = await db.violations.findAsync({ ...scope(req) });
    const counted = all.filter((v) => COUNTED.includes(v.status));
    const byItem = {};
    counted.forEach((v) => v.missing.split(/\s*[,+]\s*/).map((s) => s.trim()).filter(Boolean).forEach((m) => { byItem[m] = (byItem[m] || 0) + 1; }));
    const days = Array.from({ length: 14 }, (_, i) => new Date(Date.now() - (13 - i) * 86400000).toISOString().slice(0, 10));
    const penalties = await db.penalties.findAsync({ ...scope(req) });
    const tally = (key) => counted.reduce((m, v) => { const k = key(v); if (k) m[k] = (m[k] || 0) + 1; return m; }, {});
    const byEmployee = Object.entries(tally((v) => v.employeeName)).sort((a, b) => b[1] - a[1]).slice(0, 5);
    res.json({
      byEmployee, byLocation: tally((v) => v.location),
      caughtToday: all.filter((v) => v.dayKey === dayKey(now(), policy.timezoneOffsetMinutes ?? 330)).reduce((n, v) => n + (v.catches || 1), 0),
      peopleToday: new Set(all.filter((v) => v.dayKey === dayKey(now(), policy.timezoneOffsetMinutes ?? 330)).map((v) => v.suggested?.employeeId || v.employeeName || v._id)).size,
      pending: all.filter((v) => v.status === 'Pending review').length, confirmed: counted.length, dismissed: all.filter((v) => v.status === 'Dismissed').length,
      disputed: all.filter((v) => v.status === 'Disputed').length, byItem, series: days.map((d) => counted.filter((v) => String(v.occurredAt).slice(0, 10) === d).length), days,
      penaltiesWaiting: penalties.filter((p) => ['Proposed', 'Disputed'].includes(p.status)).length,
      penaltyTotal: penalties.filter((p) => ['Issued', 'Paid'].includes(p.status)).reduce((s, p) => s + p.amount, 0),
    });
  }));

  // ---- employee ------------------------------------------------------------------------------
  const me = guarded('employee');

  me.get('/me/violations', wrap(async (req, res) => res.json(await db.violations.findAsync({ employeeId: req.user.id, status: { $in: COUNTED } }).sort({ number: -1 }))));
  me.get('/me/penalties', wrap(async (req, res) => res.json(await db.penalties.findAsync({ employeeId: req.user.id, status: { $ne: 'Proposed' } }).sort({ createdAt: -1 }))));
  me.get('/me/summary', wrap(async (req, res) => {
    const violations = await db.violations.findAsync({ employeeId: req.user.id, status: { $in: COUNTED } });
    const penalties = await db.penalties.findAsync({ employeeId: req.user.id });
    const issued = penalties.filter((p) => p.status === 'Issued');
    res.json({
      violations: violations.length, awaitingResponse: violations.filter((v) => v.status === 'Confirmed').length, penaltiesIssued: penalties.filter((p) => ['Issued', 'Paid'].includes(p.status)).length,
      amountDue: issued.reduce((s, p) => s + p.amount, 0), currency: policy.currency, proposeAt: policy.proposeAt, windowDays: policy.windowDays,
    });
  }));

  // Everything that happened to this employee, newest first: every catch with its date, time, place and how it was caught,
  // including cases still waiting for a supervisor to confirm them.
  me.get('/me/feed', wrap(async (req, res) => {
    const u = await db.users.findOneAsync({ _id: req.user.id });
    const cases = await db.violations.findAsync({ $or: [{ employeeId: u._id }, { employeeId: null, 'suggested.employeeId': u.employeeId }] });
    const events = [];
    for (const v of cases) {
      const base = { caseNumber: v.number, status: v.status, missing: v.missing, location: v.location, source: v.source, evidencePath: v.evidencePath, remarks: v.remarks || '', reason: v.reason || '' };
      events.push({ ...base, at: v.occurredAt, kind: 'caught', text: `Caught without ${itemsOf(v.missing).map((i) => i.replace(/^NO /, '').toLowerCase()).join(' and ')}` });
      for (const l of v.log || []) if (l.action === 'Caught again') events.push({ ...base, at: l.at, kind: 'again', text: `Caught again: ${l.note}` });
    }
    res.json(events.sort((a, b) => new Date(b.at) - new Date(a.at)));
  }));

  me.get('/me/violations/:id/notice.pdf', wrap(async (req, res) => {
    const v = await db.violations.findOneAsync({ _id: req.params.id, employeeId: req.user.id });
    if (!v || !COUNTED.includes(v.status)) return res.status(404).json({ error: 'No such violation.' });  // an employee sees only their own confirmed violations
    await sendNotice(res, v, `${req.user.name} (employee copy)`);
  }));

  me.get('/me/report.pdf', wrap(async (req, res) => {
    const u = await db.users.findOneAsync({ _id: req.user.id });
    await sendReport(res, u, `${u.name} (employee copy)`);
  }));

  me.get('/me/profile', wrap(async (req, res) => {
    const u = await db.users.findOneAsync({ _id: req.user.id });
    res.json({ ...publicUser(u), monthlySalary: u.monthlySalary || 0, currency: policy.currency });
  }));
  me.get('/me/salary', wrap(async (req, res) => {
    const u = await db.users.findOneAsync({ _id: req.user.id });
    const penalties = await db.penalties.findAsync({ employeeId: u._id });
    res.json({ monthlySalary: u.monthlySalary || 0, currency: policy.currency, payslips: payslips(u.monthlySalary, penalties) });
  }));

  me.post('/violations/:id/respond', wrap(async (req, res) => {
    const v = await db.violations.findOneAsync({ _id: req.params.id, employeeId: req.user.id });
    if (!v) return res.status(404).json({ error: 'No such violation.' });
    const { action, note = '' } = req.body || {};
    if (!['acknowledge', 'dispute'].includes(action)) return res.status(400).json({ error: "Action must be 'acknowledge' or 'dispute'." });
    if (action === 'dispute' && !String(note).trim()) return res.status(400).json({ error: 'Please explain why you are disputing it.' });
    const status = action === 'acknowledge' ? 'Acknowledged' : 'Disputed';
    await db.violations.updateAsync({ _id: v._id }, { $set: { status }, $push: { log: { at: now(), by: req.user.name, action: status, note } } });
    if (action === 'dispute') await notify({ toRole: 'supervisor', message: `${req.user.name} disputed violation #${v.number}. Please look at it again.` });
    res.json({ status });
  }));

  me.post('/penalties/:id/dispute', wrap(async (req, res) => {
    const p = await db.penalties.findOneAsync({ _id: req.params.id, employeeId: req.user.id });
    if (!p) return res.status(404).json({ error: 'No such penalty.' });
    if (p.status !== 'Issued') return res.status(409).json({ error: 'Only an issued penalty can be disputed.' });
    const note = String(req.body?.note || '').trim();
    if (!note) return res.status(400).json({ error: 'Please explain why you are disputing it.' });
    await db.penalties.updateAsync({ _id: p._id }, { $set: { status: 'Disputed', note } });
    await notify({ toRole: 'supervisor', message: `${req.user.name} disputed a penalty of ${p.currency} ${p.amount}. Please review.` });
    res.json({ status: 'Disputed' });
  }));

  // ---- both roles ----------------------------------------------------------------------------
  app.get('/api/notifications', auth, wrap(async (req, res) => {
    const q = req.user.role === 'supervisor'
      ? { toRole: 'supervisor', ...(req.user.isAdmin || !req.user.sectorId ? {} : { sectorId: { $in: [null, req.user.sectorId] } }) }
      : { $or: [{ toUserId: req.user.id }, { toRole: req.user.role }] };
    res.json(await db.notifications.findAsync(q).sort({ at: -1 }).limit(40));
  }));

  app.use((err, req, res, next) => {
    console.error(err);
    res.status(500).json({ error: 'Something went wrong on the server.' });
  });
  return app;
}
