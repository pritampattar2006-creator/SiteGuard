// Demo accounts, and (with `node src/seed.js --demo`) a made-up case history built through the real API, for presentations.
// Everything here is invented. Sign-in for the dummy accounts follows one simple pattern: the ID is the user name, and the
// password is 123456789 for the supervisors that exist now (S001, S002, S003) and for every employee (E001 to E120). Supervisors made later choose their own. Change this for real use.
import bcrypt from 'bcryptjs';
import { EMPLOYEE_PASSWORD, PRESENT_SUPERVISOR_PASSWORD } from './defaults.js';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const demoPassword = (employeeId) => `${employeeId}@123`;

// Kinds of work, each with the gear its workers must wear. These are STARTING values for the demo: the site's safety officer
// confirms the real list for each kind of work (the head supervisor can change it in the supervisor panel).
export const SECTORS = [
  { name: 'Civil Construction Site', conditionClass: 'Class A: general construction', requiredItems: ['helmet', 'vest', 'boots'], location: 'Main site', fields: ['Block A', 'Block B', 'Foundation', 'Scaffolding'], classes: ['Class A: general construction', 'Class A2: work at height'] },
  { name: 'Electrical Wiring Works', conditionClass: 'Class B: electrical wiring work', requiredItems: ['helmet', 'gloves', 'boots'], location: 'Wiring block', fields: ['Panel room', 'Cable trench', 'Floor wiring'], classes: ['Class B: electrical wiring work'] },
  { name: 'Power Line Works', conditionClass: 'Class C: overhead and live-line work', requiredItems: ['helmet', 'vest', 'gloves', 'boots'], location: 'Line section', fields: ['Pole line', 'Substation yard', 'Transformer bay'], classes: ['Class C: overhead and live-line work'] },
];

// One supervisor per kind of work. S001 is the head supervisor: sees every sector and sets up sectors and supervisors.
export const SUPERVISORS = [
  { employeeId: 'S001', monthlySalary: 60000, jobRole: 'Head supervisor', name: 'Priya Menon', department: 'Site safety', role: 'supervisor', isAdmin: true, sector: 'Civil Construction Site', code: 'BCE' },
  { employeeId: 'S002', monthlySalary: 52000, jobRole: 'Supervisor', name: 'Ramesh Kamat', department: 'Electrical Wiring Works', role: 'supervisor', isAdmin: false, sector: 'Electrical Wiring Works', code: 'BWE' },
  { employeeId: 'S003', monthlySalary: 52000, jobRole: 'Supervisor', name: 'Anita Deshpande', department: 'Power Line Works', role: 'supervisor', isAdmin: false, sector: 'Power Line Works', code: 'BLE' },
];

// Made-up employees E001, E002, ...: the same people the detector names when it recognises a face (config/dummy_roster.json).
function loadRoster() {
  try { return JSON.parse(fs.readFileSync(path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'config', 'dummy_roster.json'), 'utf8')).employees; } catch { return []; }
}

// Professional names for the kinds of work (the places workers actually work, not the trade). Databases made earlier have the old names: they are renamed
// ONCE here (and every later start finds nothing left to do). Names already in use are never overwritten. "wwelding" was a typo made when a sector was typed in.
export const SECTOR_RENAMES = {
  Construction: 'Civil Construction Site',
  Wireman: 'Electrical Wiring Works',
  Lineman: 'Power Line Works',
  Welding: 'Fabrication & Welding Bay',
  wwelding: 'Fabrication & Welding Bay',
};

export async function renameSectors(db) {
  let renamed = 0;
  for (const [from, to] of Object.entries(SECTOR_RENAMES)) {
    const sector = await db.sectors.findOneAsync({ name: from });
    if (sector && !(await db.sectors.findOneAsync({ name: to }))) {
      const set = { name: to };
      if (sector.location === from) set.location = 'Fabrication bay';  // a place typed in as the old name
      await db.sectors.updateAsync({ _id: sector._id }, { $set: set });
      renamed += 1;
    }
    await db.users.updateAsync({ department: from }, { $set: { department: to } }, { multi: true });
    await db.violations.updateAsync({ sectorName: from }, { $set: { sectorName: to } }, { multi: true });
    for (const a of await db.accidents.findAsync({ $or: [{ sectorName: from }, { venue: from }, { venue: new RegExp(`^${from.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')} · `) }] })) {
      await db.accidents.updateAsync({ _id: a._id }, { $set: { sectorName: a.sectorName === from ? to : a.sectorName, venue: a.venue === from ? to : String(a.venue).replace(`${from} · `, `${to} · `) } });
    }
  }
  return renamed;
}

// Older data: give supervisors a code and sector options, and give every employee without a sector one (in three even blocks, by ID),
// so each supervisor sees a team. Safe to run on every start.
export async function backfillSectors(db) {
  const sectors = await db.sectors.findAsync({});
  const byName = Object.fromEntries(sectors.map((s) => [s.name, s]));
  for (const def of SECTORS) {
    const s = byName[def.name];
    if (s && !s.fields) await db.sectors.updateAsync({ _id: s._id }, { $set: { fields: def.fields, classes: def.classes } });
  }
  for (const def of SUPERVISORS) {
    const u = await db.users.findOneAsync({ employeeId: def.employeeId });
    if (u && !u.code) await db.users.updateAsync({ _id: u._id }, { $set: { code: def.code } });
  }
  const order = SECTORS.map((s) => byName[s.name]?._id).filter(Boolean);
  if (!order.length) return;
  const loose = (await db.users.findAsync({ role: 'employee', sectorId: { $exists: false } })).sort((a, b) => a.employeeId.localeCompare(b.employeeId));
  const block = Math.ceil(loose.length / order.length) || 1;
  for (const [i, u] of loose.entries()) await db.users.updateAsync({ _id: u._id }, { $set: { sectorId: order[Math.min(order.length - 1, Math.floor(i / block))] } });
}

// Every employee account uses one password. Accounts made earlier (with the old ID@123 pattern) are switched over ONCE, marked so it never repeats
// and never overrides a password changed later. Safe to run on every start.
export async function setEmployeePasswords(db) {
  if (await db.users.findOneAsync({ role: 'system', passwordsSet: 'employees-v1' })) return 0;
  const hash = await bcrypt.hash(EMPLOYEE_PASSWORD, 8);
  const result = await db.users.updateAsync({ role: 'employee' }, { $set: { passwordHash: hash } }, { multi: true });
  await db.users.insertAsync({ role: 'system', passwordsSet: 'employees-v1' });
  return typeof result === 'number' ? result : result.numAffected;
}

// The supervisors that exist at this moment are switched to the shared password ONCE (marked, so it never repeats, never touches supervisors made later,
// and never overrides a password changed afterwards).
export async function setPresentSupervisorPasswords(db) {
  if (await db.users.findOneAsync({ role: 'system', passwordsSet: 'supervisors-v1' })) return 0;
  const hash = await bcrypt.hash(PRESENT_SUPERVISOR_PASSWORD, 8);
  const result = await db.users.updateAsync({ role: 'supervisor', pending: { $ne: true } }, { $set: { passwordHash: hash } }, { multi: true });
  await db.users.insertAsync({ role: 'system', passwordsSet: 'supervisors-v1' });
  return typeof result === 'number' ? result : result.numAffected;
}

// Sign-up requests made while accounts still needed the head supervisor's approval were left waiting when that step was removed (a new account is now
// ready at once, with a site of its own). Settle them ONCE: approve them and give them the shared password, so no account is stuck unable to sign in.
export async function settlePendingSupervisors(db) {
  if (await db.users.findOneAsync({ role: 'system', passwordsSet: 'supervisors-pending-v1' })) return 0;
  const hash = await bcrypt.hash(PRESENT_SUPERVISOR_PASSWORD, 8);
  const result = await db.users.updateAsync({ role: 'supervisor', pending: true }, { $set: { passwordHash: hash, pending: false, approvedBy: 'Setup (old request settled)', approvedAt: new Date().toISOString() } }, { multi: true });
  await db.users.insertAsync({ role: 'system', passwordsSet: 'supervisors-pending-v1' });
  return typeof result === 'number' ? result : result.numAffected;
}

export async function seedAccounts(db) {
  // Seeding ends with a marker. If the process was stopped part-way (a restart while seeding), there is no marker, so start the demo accounts over;
  // but never touch accounts once real cases exist.
  if (await db.users.findOneAsync({ seedComplete: true })) return false;
  if ((await db.violations.countAsync({})) > 0) return false;
  await db.users.removeAsync({}, { multi: true });
  await db.sectors.removeAsync({}, { multi: true });
  const ids = {};
  for (const s of SECTORS) ids[s.name] = (await db.sectors.insertAsync({ ...s, createdAt: new Date().toISOString(), createdBy: 'Setup' }))._id;
  for (const { sector, ...u } of SUPERVISORS) {
    await db.users.insertAsync({ ...u, sectorId: ids[sector], passwordHash: await bcrypt.hash(PRESENT_SUPERVISOR_PASSWORD, 8) });
  }
  const employeeHash = await bcrypt.hash(EMPLOYEE_PASSWORD, 8); // the same for everyone, so it is made once
  for (const e of loadRoster()) await db.users.insertAsync({ ...e, role: 'employee', passwordHash: employeeHash });
  await db.users.insertAsync({ role: 'system', passwordsSet: 'employees-v1' });
  await backfillSectors(db);
  await db.users.insertAsync({ role: 'system', passwordsSet: 'supervisors-v1' });
  await db.users.insertAsync({ seedComplete: true, role: 'system' });
  console.log(`Created dummy accounts. Every account uses the password ${EMPLOYEE_PASSWORD}: supervisors S001, S002, S003 and employees E001 to E120. Supervisors created later choose their own.`);
  return true;
}

// node src/seed.js          : add a few pending cases (annotated photos from the detector project when present)
// node src/seed.js --demo   : also build a believable history through the real API (confirmed cases, a penalty), for presentations
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const base = process.env.API_URL || 'http://localhost:4000';
  const key = process.env.INGEST_KEY || 'dev-ingest-key';
  const demo = process.argv.includes('--demo');
  const folder = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'ppe-detection', 'outputs', 'cases');
  const images = fs.existsSync(folder) ? fs.readdirSync(folder).filter((f) => f.endsWith('.png')).sort() : [];
  const picture = (i) => (images.length ? { evidenceBase64: fs.readFileSync(path.join(folder, images[i % images.length])).toString('base64') } : {});
  const call = async (method, url, { token, body, headers = {} } = {}) => {
    const res = await fetch(base + url, { method, headers: { 'content-type': 'application/json', ...(token ? { authorization: `Bearer ${token}` } : {}), ...headers }, body: body ? JSON.stringify(body) : undefined });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(`${method} ${url}: ${data.error || res.status}`);
    return data;
  };
  const ingest = (items) => call('POST', '/api/ingest/violations', { headers: { 'x-ingest-key': key }, body: { items } });
  const ago = (days, hours = 0) => new Date(Date.now() - days * 86400000 - hours * 3600000).toISOString();
  const places = ['Gate 2', 'Block B', 'Scaffold C', 'Crane bay', 'Level 3 slab'];
  let n = 0;
  let sectorId = '';
  const item = (missing, daysAgo, extra = {}) => ({ sector: sectorId, workerRef: `Employee ${(n % 6) + 1}`, missing, location: places[n % places.length], source: 'demo', sourceName: 'demo', reason: 'A required item was not found on this worker.', occurredAt: ago(daysAgo, (n * 3) % 9), ...picture(n++), ...extra });

  sectorId = ((await call('GET', '/api/sectors/public')).find((x) => x.name === 'Civil Construction Site') || {}).id || '';
  if (demo) {
    const sup = (await call('POST', '/api/auth/login', { body: { employeeId: 'S001', password: PRESENT_SUPERVISOR_PASSWORD } })).token;
    const staff = Object.fromEntries((await call('GET', '/api/employees', { token: sup })).map((e) => [e.employeeId, e]));
    const login = async (id) => (await call('POST', '/api/auth/login', { body: { employeeId: id, password: id.startsWith('E') ? EMPLOYEE_PASSWORD : demoPassword(id) } })).token;
    const hint = (id) => ({ employeeId: id, name: staff[id].name, jobRole: staff[id].jobRole, department: staff[id].department, score: 1 });
    const plan = { E001: [['NO HELMET', 22], ['NO VEST', 14], ['NO HELMET', 6]], E002: [['NO HELMET, NO VEST', 11], ['NO HELMET', 3]], E003: [['NO VEST', 9]] };
    for (const [eid, cases] of Object.entries(plan)) {
      const made = await ingest(cases.map(([missing, d]) => item(missing, d, { suggested: hint(eid) })));
      for (const id of made.ids) await call('POST', `/api/violations/${id}/decision`, { token: sup, body: { decision: 'confirm', employeeId: staff[eid].id, note: 'Checked against the picture.' } });
      if (eid === 'E002') await call('POST', `/api/violations/${made.ids[0]}/respond`, { token: await login('E002'), body: { action: 'acknowledge' } });
      if (eid === 'E003') await call('POST', `/api/violations/${made.ids[0]}/respond`, { token: await login('E003'), body: { action: 'dispute', note: 'I was wearing a vest; it was under my jacket.' } });
    }
    const extra = await ingest([item('NO HELMET', 40), item('NO VEST', 2)]);
    for (const id of extra.ids) await call('POST', `/api/violations/${id}/decision`, { token: sup, body: { decision: 'dismiss', note: 'Not a worker: a visitor.' } });
    for (const p of await call('GET', '/api/penalties?status=Proposed', { token: sup })) await call('POST', `/api/penalties/${p._id}/decide`, { token: sup, body: { decision: 'Issued', note: 'Third violation in 30 days.' } });
    console.log('Demo history built.');
  }

  const pending = [item('NO HELMET', 0), item('NO VEST', 0), item('NO HELMET, NO VEST', 0, { suggested: { employeeId: 'E004', name: 'Kiran Bhat', jobRole: 'Carpenter', department: 'Rigging', score: 0.9 } }), item('UNCLEAR', 0, { reason: 'The detector was not sure. Someone is partly hidden.' })];
  console.log('Pending cases added:', (await ingest(pending)).created);
}
