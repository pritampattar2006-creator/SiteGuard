import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { createApp } from '../src/app.js';
import { openDb } from '../src/db.js';
import { DEFAULT_POLICY, newPenaltyBatches } from '../src/policy.js';
import { seedAccounts, setEmployeePasswords, setPresentSupervisorPasswords, settlePendingSupervisors } from '../src/seed.js';

let server; let base; let uploads;
const KEY = 'test-key';

async function call(method, url, { token, body, headers = {} } = {}) {
  const res = await fetch(base + url, { method, headers: { 'content-type': 'application/json', ...(token ? { authorization: `Bearer ${token}` } : {}), ...headers }, body: body ? JSON.stringify(body) : undefined });
  return { status: res.status, body: await res.json().catch(() => ({})) };
}
const login = async (id, pw) => (await call('POST', '/api/auth/login', { body: { employeeId: id, password: pw } })).body;
const ingest = (n = 1) => call('POST', '/api/ingest/violations', { headers: { 'x-ingest-key': KEY }, body: { items: Array.from({ length: n }, (_, i) => ({ workerRef: 'Worker 1', missing: 'NO HELMET', location: `Gate ${i}` })) } });

before(async () => {
  const db = await openDb(null);
  await seedAccounts(db);
  uploads = fs.mkdtempSync(path.join(os.tmpdir(), 'sg-'));
  const app = createApp({ db, policy: DEFAULT_POLICY, secret: 'test-secret', ingestKey: KEY, uploadsDir: uploads });
  await new Promise((r) => { server = app.listen(0, r); });
  base = `http://localhost:${server.address().port}`;
});
after(() => { server.close(); fs.rmSync(uploads, { recursive: true, force: true }); });

test('policy: groups of three confirmed violations in the window make one batch', () => {
  const v = (n, status = 'Confirmed', days = 1) => ({ _id: `v${n}`, status, occurredAt: new Date(Date.now() - days * 86400000).toISOString() });
  assert.equal(newPenaltyBatches([v(1), v(2)], DEFAULT_POLICY).length, 0);
  assert.equal(newPenaltyBatches([v(1), v(2), v(3)], DEFAULT_POLICY).length, 1);
  assert.equal(newPenaltyBatches([v(1), v(2), v(3, 'Dismissed')], DEFAULT_POLICY).length, 0);
  assert.equal(newPenaltyBatches([v(1), v(2), v(3, 'Pending review')], DEFAULT_POLICY).length, 0);
  assert.equal(newPenaltyBatches([v(1), v(2), v(3, 'Confirmed', 40)], DEFAULT_POLICY).length, 0);
  assert.equal(newPenaltyBatches([{ ...v(1), penaltyId: 'p' }, v(2), v(3)], DEFAULT_POLICY).length, 0);
});

test('sign in: wrong password is refused, and protected routes need a token', async () => {
  assert.equal((await call('POST', '/api/auth/login', { body: { employeeId: 'E001', password: 'nope' } })).status, 401);
  assert.equal((await call('GET', '/api/review/queue')).status, 401);
});

test('ingest needs the key', async () => {
  assert.equal((await call('POST', '/api/ingest/violations', { body: { items: [{}] } })).status, 401);
});

test('roles are kept apart', async () => {
  const emp = await login('E001', '123456789');
  const sup = await login('S001', '123456789');
  assert.equal((await call('GET', '/api/review/queue', { token: emp.token })).status, 403);
  assert.equal((await call('GET', '/api/me/violations', { token: sup.token })).status, 403);
});

test('a caught violation stays hidden from the employee until the supervisor confirms it', async () => {
  const emp = await login('E002', '123456789');
  const sup = await login('S001', '123456789');
  const made = await ingest();
  assert.equal(made.status, 201);
  assert.equal((await call('GET', '/api/me/violations', { token: emp.token })).body.length, 0);

  const queue = (await call('GET', '/api/review/queue', { token: sup.token })).body;
  assert.ok(queue.length >= 1);
  const item = queue.find((q) => q._id === made.body.ids[0]);
  assert.equal(item.employeeId, null);

  const noEmployee = await call('POST', `/api/violations/${item._id}/decision`, { token: sup.token, body: { decision: 'confirm' } });
  assert.equal(noEmployee.status, 400);

  const done = await call('POST', `/api/violations/${item._id}/decision`, { token: sup.token, body: { decision: 'confirm', employeeId: emp.user.id } });
  assert.equal(done.status, 200);
  assert.equal((await call('POST', `/api/violations/${item._id}/decision`, { token: sup.token, body: { decision: 'dismiss' } })).status, 409);

  const mine = (await call('GET', '/api/me/violations', { token: emp.token })).body;
  assert.equal(mine.length, 1);
  assert.equal(mine[0].status, 'Confirmed');
  assert.equal((await call('POST', `/api/violations/${item._id}/respond`, { token: emp.token, body: { action: 'dispute' } })).status, 400);
  assert.equal((await call('POST', `/api/violations/${item._id}/respond`, { token: emp.token, body: { action: 'acknowledge' } })).body.status, 'Acknowledged');
});

test('a dismissed violation never reaches the employee or counts', async () => {
  const emp = await login('E003', '123456789');
  const sup = await login('S001', '123456789');
  const made = await ingest(3);
  for (const id of made.body.ids) await call('POST', `/api/violations/${id}/decision`, { token: sup.token, body: { decision: 'dismiss' } });
  assert.equal((await call('GET', '/api/me/violations', { token: emp.token })).body.length, 0);
  assert.equal((await call('GET', '/api/penalties', { token: sup.token })).body.filter((p) => p.employeeName === emp.user.name).length, 0);
});

test('three confirmed violations propose a penalty that the supervisor approves and the employee can dispute', async () => {
  const emp = await login('E004', '123456789');
  const sup = await login('S001', '123456789');
  const made = await ingest(3);
  for (const id of made.body.ids) await call('POST', `/api/violations/${id}/decision`, { token: sup.token, body: { decision: 'confirm', employeeId: emp.user.id } });

  assert.equal((await call('GET', '/api/me/penalties', { token: emp.token })).body.length, 0, 'a proposed penalty is hidden from the employee');
  const proposed = (await call('GET', '/api/penalties?status=Proposed', { token: sup.token })).body.filter((p) => p.employeeId === emp.user.id);
  assert.equal(proposed.length, 1);
  assert.equal(proposed[0].violationIds.length, 3);

  assert.equal((await call('POST', `/api/penalties/${proposed[0]._id}/decide`, { token: sup.token, body: { decision: 'Paid' } })).status, 400);
  assert.equal((await call('POST', `/api/penalties/${proposed[0]._id}/decide`, { token: sup.token, body: { decision: 'Issued' } })).status, 200);

  const visible = (await call('GET', '/api/me/penalties', { token: emp.token })).body;
  assert.equal(visible[0].status, 'Issued');
  assert.equal((await call('POST', `/api/penalties/${visible[0]._id}/dispute`, { token: emp.token, body: {} })).status, 400);
  assert.equal((await call('POST', `/api/penalties/${visible[0]._id}/dispute`, { token: emp.token, body: { note: 'wrong person' } })).body.status, 'Disputed');
  assert.equal((await call('POST', `/api/penalties/${proposed[0]._id}/decide`, { token: sup.token, body: { decision: 'Waived' } })).status, 200);
});

test('a face-match suggestion is kept as a hint only: the case still waits for the supervisor and nothing is named', async () => {
  const sup = await login('S001', '123456789');
  const made = await call('POST', '/api/ingest/violations', { headers: { 'x-ingest-key': KEY }, body: { items: [{ missing: 'NO VEST', suggested: { employeeId: 'E001', name: 'Asha Rao', jobRole: 'Mason', score: 0.61 } }] } });
  const item = (await call('GET', '/api/review/queue', { token: sup.token })).body.find((q) => q._id === made.body.ids[0]);
  assert.equal(item.status, 'Pending review');
  assert.equal(item.employeeId, null);
  assert.equal(item.suggested.employeeId, 'E001');
  const emp = await login('E001', '123456789');
  assert.ok(!(await call('GET', '/api/me/violations', { token: emp.token })).body.some((v) => v._id === item._id));
});

test('one violation per person per day: a repeat catch the same day only counts up, a new day starts a new case', async () => {
  const sup = await login('S001', '123456789');
  const emp = await login('E002', '123456789');
  const hint = { employeeId: 'E002', name: 'Ravi Kumar', jobRole: 'Electrician' };
  const send = (missing, occurredAt) => call('POST', '/api/ingest/violations', { headers: { 'x-ingest-key': KEY }, body: { items: [{ missing, location: 'Gate 2', suggested: hint, occurredAt }] } });
  const day1 = '2030-03-10T05:00:00.000Z';
  const first = await send('NO HELMET', day1);
  assert.deepEqual([first.body.created, first.body.repeats], [1, 0]);
  const again = await send('NO VEST', '2030-03-10T08:30:00.000Z');
  assert.deepEqual([again.body.created, again.body.repeats], [0, 1]);
  assert.equal(again.body.ids[0], first.body.ids[0]);
  const queue = (await call('GET', '/api/review/queue', { token: sup.token })).body.filter((q) => q.suggested?.employeeId === 'E002' && q.dayKey === '2030-03-10');
  assert.equal(queue.length, 1);
  assert.equal(queue[0].catches, 2);
  assert.equal(queue[0].missing, 'NO HELMET, NO VEST');
  const nextDay = await send('NO HELMET', '2030-03-11T05:00:00.000Z');
  assert.deepEqual([nextDay.body.created, nextDay.body.repeats], [1, 0]);
  const notes = (await call('GET', '/api/notifications', { token: emp.token })).body;
  assert.ok(notes.some((n) => /Safety alert/.test(n.message)), 'the employee is told straight away');
});

test('an unnamed catch is not repeated every few seconds', async () => {
  const one = () => call('POST', '/api/ingest/violations', { headers: { 'x-ingest-key': KEY }, body: { items: [{ missing: 'NO HELMET', location: 'Crane bay' }] } });
  const a = await one();
  const b = await one();
  assert.deepEqual([a.body.created, b.body.created, b.body.repeats], [1, 0, 1]);
});

test('a photo can be set for an employee, and only as a small image', async () => {
  const sup = await login('S001', '123456789');
  const e = (await call('GET', '/api/employees', { token: sup.token })).body.find((x) => x.employeeId === 'E003');
  const tiny = 'data:image/png;base64,iVBORw0KGgo=';
  assert.equal((await call('POST', `/api/employees/${e.id}/photo`, { token: sup.token, body: { photo: tiny } })).status, 200);
  assert.equal((await call('GET', '/api/employees', { token: sup.token })).body.find((x) => x.employeeId === 'E003').photo, tiny);
  assert.equal((await call('POST', `/api/employees/${e.id}/photo`, { token: sup.token, body: { photo: 'http://evil/x.png' } })).status, 400);
});

test('two unnamed people in the same picture stay two separate cases', async () => {
  const items = [{ missing: 'NO VEST', location: 'Block Z' }, { missing: 'NO VEST', location: 'Block Z' }];
  const r = await call('POST', '/api/ingest/violations', { headers: { 'x-ingest-key': KEY }, body: { items } });
  assert.deepEqual([r.body.created, r.body.repeats], [2, 0]);
  const again = await call('POST', '/api/ingest/violations', { headers: { 'x-ingest-key': KEY }, body: { items: [items[0]] } });
  assert.equal(again.body.repeats, 1, 'but the next picture a minute later is the same group, not new people');
});

test('every case gets a short factual remark, which a supervisor can edit and which is then kept', async () => {
  const sup = await login('S001', '123456789');
  const hint = { employeeId: 'E004', name: 'Kiran Patil', jobRole: 'Site engineer' };
  const r = await call('POST', '/api/ingest/violations', { headers: { 'x-ingest-key': KEY }, body: { items: [{ missing: 'NO HELMET, NO VEST', location: 'Gate 5', suggested: hint, occurredAt: '2031-01-05T05:00:00.000Z' }] } });
  const get = async () => (await call('GET', '/api/review/queue', { token: sup.token })).body.find((q) => q._id === r.body.ids[0]);
  const first = await get();
  const e4 = (await call('GET', '/api/employees', { token: sup.token })).body.find((x) => x.employeeId === 'E004');
  assert.ok(first.remarks.startsWith(`${e4.name} (${e4.jobRole}) was seen without helmet and vest at Gate 5`), first.remarks);
  assert.match(first.remarks, /First violation in the last 30 days|earlier violation/);
  await call('POST', `/api/violations/${first._id}/remarks`, { token: sup.token, body: { remarks: 'Was carrying the helmet in his hand.' } });
  await call('POST', '/api/ingest/violations', { headers: { 'x-ingest-key': KEY }, body: { items: [{ missing: 'NO HELMET', location: 'Gate 5', suggested: hint, occurredAt: '2031-01-05T09:00:00.000Z' }] } });
  assert.equal((await get()).remarks, 'Was carrying the helmet in his hand.', 'an edited remark is not overwritten');
});

test('sectors: each kind of work has its own required gear and its own supervisor, who only sees their own cases', async () => {
  const head = await login('S001', '123456789');
  const wire = await login('S002', '123456789');
  const line = await login('S003', '123456789');
  const sectors = (await call('GET', '/api/sectors/public')).body;
  const wireman = sectors.find((s) => s.name === 'Electrical Wiring Works');
  assert.deepEqual(wireman.requiredItems, ['helmet', 'gloves', 'boots']);
  assert.ok(wireman.supervisors.includes('Ramesh Kamat'));

  const made = await call('POST', '/api/ingest/violations', { headers: { 'x-ingest-key': KEY }, body: { items: [{ missing: 'NO GLOVES', location: 'Wiring block', sector: wireman.id }] } });
  const inQueue = async (who) => (await call('GET', '/api/review/queue', { token: who.token })).body.some((q) => q._id === made.body.ids[0]);
  assert.equal(await inQueue(head), true, 'the head supervisor sees every sector');
  assert.equal(await inQueue(wire), true, 'the wireman supervisor sees their own case');
  assert.equal(await inQueue(line), false, 'the lineman supervisor does not');
  assert.equal((await call('POST', `/api/violations/${made.body.ids[0]}/decision`, { token: line.token, body: { decision: 'dismiss' } })).status, 403);
  assert.equal((await call('POST', `/api/violations/${made.body.ids[0]}/decision`, { token: wire.token, body: { decision: 'dismiss' } })).status, 200);
});

test('only the head supervisor can create sectors and supervisors; a new supervisor gets a code and a password', async () => {
  const head = await login('S001', '123456789');
  const wire = await login('S002', '123456789');
  const body = { name: 'Plumbing', conditionClass: 'Class D', requiredItems: ['helmet', 'gloves', 'bogus'], location: 'Block P' };
  assert.equal((await call('POST', '/api/sectors', { token: wire.token, body })).status, 403);
  assert.equal((await call('POST', '/api/sectors', { token: head.token, body: { ...body, requiredItems: [] } })).status, 400);
  const made = await call('POST', '/api/sectors', { token: head.token, body });
  assert.equal(made.status, 201);
  assert.deepEqual(made.body.requiredItems, ['helmet', 'gloves'], 'unknown items are dropped');
  assert.equal((await call('POST', '/api/sectors', { token: head.token, body })).status, 409, 'no duplicate names');

  assert.equal((await call('POST', '/api/supervisors', { token: wire.token, body: { name: 'X', sectorId: made.body.id } })).status, 403);
  assert.equal((await call('POST', '/api/supervisors', { token: head.token, body: { name: 'Meena Rao' } })).status, 400, 'a sector must be chosen');
  const sup = await call('POST', '/api/supervisors', { token: head.token, body: { name: 'Meena Rao', sectorId: made.body.id } });
  assert.equal(sup.status, 201);
  assert.match(sup.body.employeeId, /^S\d{3}$/);
  assert.equal(sup.body.password, `${sup.body.employeeId}@123`);
  const again = await login(sup.body.employeeId, sup.body.password);
  assert.equal(again.user.sectorName, 'Plumbing');
  assert.equal(again.user.isAdmin, false);
});

test('a supervisor adds an employee: the ID is their 3-letter code plus a number, the starting password is the default, and only their sector sees them', async () => {
  const head = await login('S001', '123456789');
  const wire = await login('S002', '123456789');
  const made = await call('POST', '/api/employees', { token: wire.token, body: { name: 'Test Wireman', jobRole: 'Electrician', field: 'Panel room', className: 'Class B: electrical wiring work' } });
  assert.equal(made.status, 201, JSON.stringify(made.body));
  assert.equal(made.body.employeeId, 'BWE101');
  assert.equal(made.body.password, '123456789');
  const again = await call('POST', '/api/employees', { token: wire.token, body: { name: 'Second One', number: '123' } });
  assert.equal(again.body.employeeId, 'BWE123');
  assert.equal((await call('POST', '/api/employees', { token: wire.token, body: { name: 'Third', number: '123' } })).status, 409);
  assert.equal((await call('POST', '/api/employees', { token: wire.token, body: { name: 'Bad field', field: 'Moon base' } })).status, 400);
  const signedIn = await login('BWE101', '123456789');
  assert.equal(signedIn.user.name, 'Test Wireman');
  const lineSup = await login('S003', '123456789');
  assert.ok(!(await call('GET', '/api/employees', { token: lineSup.token })).body.some((e) => e.employeeId === 'BWE101'), 'another sector must not see them');
  assert.ok((await call('GET', '/api/employees', { token: head.token })).body.some((e) => e.employeeId === 'BWE101'));
});

test('a new supervisor gets a unique 3-letter code, and a supervisor edits the fields and classes of their own sector only', async () => {
  const head = await login('S001', '123456789');
  const sectors = (await call('GET', '/api/sectors', { token: head.token })).body;
  const sector = sectors.find((s) => s.name === 'Civil Construction Site');
  const sup = await call('POST', '/api/supervisors', { token: head.token, body: { name: 'Code Test', sectorId: sector.id } });
  assert.match(sup.body.code, /^[A-Z]{3}$/);
  assert.equal((await call('POST', '/api/supervisors', { token: head.token, body: { name: 'Same Code', sectorId: sector.id, code: sup.body.code } })).status, 409);
  assert.equal((await call('POST', '/api/supervisors', { token: head.token, body: { name: 'Bad', sectorId: sector.id, code: 'AB1' } })).status, 400);
  const wire = await login('S002', '123456789');
  const mine = (await call('GET', '/api/sectors', { token: wire.token })).body.find((s) => s.name === 'Electrical Wiring Works');
  const saved = await call('POST', `/api/sectors/${mine.id}/options`, { token: wire.token, body: { fields: ['Panel room', 'Roof', 'Roof'], classes: 'Class B, Class B2' } });
  assert.deepEqual(saved.body.fields, ['Panel room', 'Roof']);
  assert.deepEqual(saved.body.classes, ['Class B', 'Class B2']);
  assert.equal((await call('POST', `/api/sectors/${sector.id}/options`, { token: wire.token, body: { fields: ['x'] } })).status, 403);
});

test('a worker-down alert becomes an accident report, raises a notification for that sector only, and shows in the log', async () => {
  const wire = await login('S002', '123456789');
  const line = await login('S003', '123456789');
  const sector = (await call('GET', '/api/sectors/public')).body.find((s) => s.name === 'Electrical Wiring Works');
  assert.equal((await call('POST', '/api/ingest/accidents', { body: {} })).status, 401);
  const r = await call('POST', '/api/ingest/accidents', { headers: { 'x-ingest-key': KEY }, body: { sector: sector.id, location: 'Wiring block', detail: 'Lying still for 6 s', suggested: { employeeId: 'E050', name: 'Someone' } } });
  assert.equal(r.status, 201);
  const open = (await call('GET', '/api/accidents?status=Open', { token: wire.token })).body;
  assert.equal(open.length, 1);
  assert.match(open[0].venue, /Electrical Wiring Works/);
  assert.equal((await call('GET', '/api/accidents?status=Open', { token: line.token })).body.length, 0);
  assert.ok((await call('GET', '/api/notifications', { token: wire.token })).body.some((n) => n.accident && /ACCIDENT ALERT/.test(n.message)));
  const log = (await call('GET', '/api/log', { token: wire.token })).body;
  assert.ok(log.some((row) => row.kind === 'Accident' && row.location.includes('Wiring block')));
  assert.equal((await call('POST', `/api/accidents/${open[0]._id}/status`, { token: wire.token, body: { status: 'Acknowledged' } })).status, 200);
  assert.equal((await call('POST', `/api/accidents/${open[0]._id}/status`, { token: line.token, body: { status: 'Resolved' } })).status, 404);
  assert.equal((await call('GET', '/api/accidents?status=Open', { token: wire.token })).body.length, 0);
});

test('a new supervisor creates an account on the sign-in page with a site of their own, signs in, sets it up, and sees nothing of anyone else', async () => {
  assert.equal((await call('POST', '/api/auth/signup', { body: { name: '', siteName: 'Bridge', requiredItems: ['helmet'], password: 'secret1' } })).status, 400);
  assert.equal((await call('POST', '/api/auth/signup', { body: { name: 'New Boss', siteName: 'Bridge', requiredItems: [], password: 'secret1' } })).status, 400);
  assert.equal((await call('POST', '/api/auth/signup', { body: { name: 'New Boss', siteName: 'Bridge', requiredItems: ['helmet'], password: '123' } })).status, 400);
  assert.equal((await call('POST', '/api/auth/signup', { body: { name: 'New Boss', siteName: 'Electrical Wiring Works', requiredItems: ['helmet'], password: 'secret1' } })).status, 409);
  const made = await call('POST', '/api/auth/signup', { body: { name: 'New Boss', siteName: 'Bridge', requiredItems: ['helmet', 'gloves'], fields: 'Pier 1, Pier 2', password: 'secret1' } });
  assert.equal(made.status, 201, JSON.stringify(made.body));
  assert.match(made.body.code, /^[A-Z]{3}$/);
  const boss = await login(made.body.employeeId, 'secret1');
  assert.equal(boss.user.role, 'supervisor');
  assert.equal(boss.user.isAdmin, false);
  assert.equal(boss.user.sectorName, 'Bridge');
  // their own site, with their own requirements, and no one else's
  const sectors = (await call('GET', '/api/sectors', { token: boss.token })).body;
  assert.deepEqual(sectors.map((s) => s.name), ['Bridge']);
  assert.deepEqual(sectors[0].requiredItems, ['helmet', 'gloves']);
  assert.deepEqual(sectors[0].fields, ['Pier 1', 'Pier 2']);
  assert.equal((await call('GET', '/api/employees', { token: boss.token })).body.length, 0);
  assert.equal((await call('GET', '/api/supervisors', { token: boss.token })).body.length, 1);
  assert.equal((await call('GET', '/api/review/queue', { token: boss.token })).body.length, 0);
  // they can change their own requirements, not anyone else's, and add employees with IDs from their own code
  assert.equal((await call('POST', `/api/sectors/${sectors[0].id}`, { token: boss.token, body: { name: 'Bridge', requiredItems: ['helmet', 'vest', 'boots'] } })).status, 200);
  const other = (await call('GET', '/api/sectors/public')).body.find((s) => s.name === 'Electrical Wiring Works');
  assert.equal((await call('POST', `/api/sectors/${other.id}`, { token: boss.token, body: { name: 'Electrical Wiring Works', requiredItems: ['helmet'] } })).status, 403);
  const worker = await call('POST', '/api/employees', { token: boss.token, body: { name: 'Pier Worker', field: 'Pier 1' } });
  assert.equal(worker.body.employeeId, `${made.body.code}101`);
  assert.equal((await call('GET', '/api/employees', { token: boss.token })).body.length, 1);
});


test('the employee complaint report is a real PDF, for the supervisor of that sector and for the employee, and nobody else', async () => {
  const head = await login('S001', '123456789');
  const wire = await login('S002', '123456789');
  const emp = await login('E003', '123456789');
  const target = (await call('GET', '/api/employees', { token: head.token })).body.find((e) => e.employeeId === 'E003');
  const made = await ingest();
  await call('POST', `/api/violations/${made.body.ids[0]}/decision`, { token: head.token, body: { decision: 'confirm', employeeId: target.id, note: 'Checked.' } });
  const pdf = async (path, token) => { const res = await fetch(base + path, { headers: token ? { authorization: `Bearer ${token}` } : {} }); return { status: res.status, type: res.headers.get('content-type'), bytes: Buffer.from(await res.arrayBuffer()) }; };
  const forSupervisor = await pdf(`/api/employees/${target.id}/report.pdf`, head.token);
  assert.equal(forSupervisor.status, 200);
  assert.equal(forSupervisor.type, 'application/pdf');
  assert.equal(forSupervisor.bytes.subarray(0, 5).toString(), '%PDF-');
  assert.ok(forSupervisor.bytes.length > 3000);
  const own = await pdf('/api/me/report.pdf', emp.token);
  assert.equal(own.status, 200);
  assert.equal(own.bytes.subarray(0, 5).toString(), '%PDF-');
  assert.equal((await pdf(`/api/employees/${target.id}/report.pdf`, null)).status, 401);
  assert.equal((await pdf(`/api/employees/${target.id}/report.pdf`, emp.token)).status, 403);           // an employee cannot ask for someone else's
  assert.equal((await pdf(`/api/employees/${target.id}/report.pdf`, wire.token)).status, 404);          // a supervisor of another sector cannot see this employee
});


test('every employee account uses the same password, 123456789, and the old ID@123 pattern no longer works for employees', async () => {
  const head = await login('S001', '123456789');
  const all = (await call('GET', '/api/employees', { token: head.token })).body;
  assert.ok(all.length >= 100);
  for (const e of [all[0], all[all.length - 1], all.find((x) => x.employeeId === 'E050')]) {
    assert.equal((await call('POST', '/api/auth/login', { body: { employeeId: e.employeeId, password: '123456789' } })).status, 200, e.employeeId);
    assert.equal((await call('POST', '/api/auth/login', { body: { employeeId: e.employeeId, password: `${e.employeeId}@123` } })).status, 401, e.employeeId);
  }
  // an employee a supervisor adds gets the same password even if another one is typed
  const made = await call('POST', '/api/employees', { token: head.token, body: { name: 'Same Password', password: 'something-else-1', sectorId: head.user.sectorId } });
  assert.equal(made.status, 201, JSON.stringify(made.body));
  assert.equal(made.body.password, '123456789');
  assert.equal((await call('POST', '/api/auth/login', { body: { employeeId: made.body.employeeId, password: '123456789' } })).status, 200);
});

test('accounts made earlier are switched to the one employee password once, and never again', async () => {
  const db = await openDb(null);
  const bcrypt = (await import('bcryptjs')).default;
  await db.users.insertAsync({ employeeId: 'E900', role: 'employee', name: 'Old', passwordHash: await bcrypt.hash('E900@123', 4) });
  await db.users.insertAsync({ employeeId: 'S900', role: 'supervisor', name: 'Boss', passwordHash: await bcrypt.hash('S900@123', 4) });
  assert.equal(await setEmployeePasswords(db), 1);                                   // the employee was switched
  assert.equal(await setEmployeePasswords(db), 0);                                   // and it is not done a second time
  const emp = await db.users.findOneAsync({ employeeId: 'E900' });
  const sup = await db.users.findOneAsync({ employeeId: 'S900' });
  assert.ok(await bcrypt.compare('123456789', emp.passwordHash));
  assert.ok(await bcrypt.compare('S900@123', sup.passwordHash));                    // supervisors untouched
  await db.users.updateAsync({ employeeId: 'E900' }, { $set: { passwordHash: await bcrypt.hash('later-choice', 4) } });
  await setEmployeePasswords(db);
  assert.ok(await bcrypt.compare('later-choice', (await db.users.findOneAsync({ employeeId: 'E900' })).passwordHash)); // a later change is never overwritten
});


test('the supervisors that exist now sign in with 123456789 (not the old ID@123), and a supervisor made later still has their own password', async () => {
  for (const id of ['S001', 'S002', 'S003']) {
    assert.equal((await call('POST', '/api/auth/login', { body: { employeeId: id, password: '123456789' } })).status, 200, id);
    assert.equal((await call('POST', '/api/auth/login', { body: { employeeId: id, password: `${id}@123` } })).status, 401, id);
  }
  const head = await login('S001', '123456789');
  const sector = (await call('GET', '/api/sectors', { token: head.token })).body[0];
  const later = await call('POST', '/api/supervisors', { token: head.token, body: { name: 'Made Later', sectorId: sector.id } });
  assert.equal(later.status, 201);
  assert.equal((await call('POST', '/api/auth/login', { body: { employeeId: later.body.employeeId, password: '123456789' } })).status, 401);  // not the shared one
  assert.equal((await call('POST', '/api/auth/login', { body: { employeeId: later.body.employeeId, password: later.body.password } })).status, 200);
});

test('supervisors that exist are switched to the shared password once, and later ones are never touched', async () => {
  const db = await openDb(null);
  const bcrypt = (await import('bcryptjs')).default;
  await db.users.insertAsync({ employeeId: 'S910', role: 'supervisor', name: 'Present', passwordHash: await bcrypt.hash('S910@123', 4) });
  await db.users.insertAsync({ employeeId: 'E910', role: 'employee', name: 'Worker', passwordHash: await bcrypt.hash('E910@123', 4) });
  assert.equal(await setPresentSupervisorPasswords(db), 1);
  assert.equal(await setPresentSupervisorPasswords(db), 0);
  await db.users.insertAsync({ employeeId: 'S911', role: 'supervisor', name: 'Later', passwordHash: await bcrypt.hash('own-choice-1', 4) });
  assert.equal(await setPresentSupervisorPasswords(db), 0);                          // a supervisor made after the switch is left alone
  assert.ok(await bcrypt.compare('123456789', (await db.users.findOneAsync({ employeeId: 'S910' })).passwordHash));
  assert.ok(await bcrypt.compare('own-choice-1', (await db.users.findOneAsync({ employeeId: 'S911' })).passwordHash));
  assert.ok(await bcrypt.compare('E910@123', (await db.users.findOneAsync({ employeeId: 'E910' })).passwordHash)); // employees are handled by their own switch
});


test('a sign-up request left waiting from the old approval step is settled once, so that account can sign in', async () => {
  const db = await openDb(null);
  const bcrypt = (await import('bcryptjs')).default;
  await db.users.insertAsync({ employeeId: 'S920', role: 'supervisor', name: 'Waiting', pending: true, passwordHash: await bcrypt.hash('typed-by-them', 4) });
  await db.users.insertAsync({ employeeId: 'S921', role: 'supervisor', name: 'Normal', passwordHash: await bcrypt.hash('own-choice-2', 4) });
  assert.equal(await settlePendingSupervisors(db), 1);
  assert.equal(await settlePendingSupervisors(db), 0);                               // once only
  const waiting = await db.users.findOneAsync({ employeeId: 'S920' });
  assert.equal(waiting.pending, false);
  assert.ok(await bcrypt.compare('123456789', waiting.passwordHash));
  assert.ok(await bcrypt.compare('own-choice-2', (await db.users.findOneAsync({ employeeId: 'S921' })).passwordHash)); // others untouched
});


test('a supervisor can put a penalty on an employee ID that has confirmed violations, and only then', async () => {
  const sup = await login('S001', '123456789');
  const emp = await login('E007', '123456789');
  const none = await call('POST', '/api/penalties', { token: sup.token, body: { employeeId: 'E007' } });
  assert.equal(none.status, 400, 'no confirmed violation: nothing to base a penalty on');
  assert.equal((await call('POST', '/api/penalties', { token: sup.token, body: { employeeId: 'NOPE' } })).status, 404);
  assert.equal((await call('POST', '/api/penalties', { token: emp.token, body: { employeeId: 'E007' } })).status, 403, 'an employee cannot put penalties');

  const made = await ingest(2);
  for (const id of made.body.ids) await call('POST', `/api/violations/${id}/decision`, { token: sup.token, body: { decision: 'confirm', employeeId: emp.user.id } });
  assert.equal((await call('POST', '/api/penalties', { token: sup.token, body: { employeeId: 'E007', amount: 0 } })).status, 400, 'a zero amount is refused');
  assert.equal((await call('POST', '/api/penalties', { token: sup.token, body: { employeeId: 'E007', violationIds: ['not-mine'] } })).status, 400);

  const made1 = await call('POST', '/api/penalties', { token: sup.token, body: { employeeId: 'e007', violationIds: [made.body.ids[0]], amount: 250, reason: 'Repeated no helmet' } });
  assert.equal(made1.status, 201);
  assert.equal(made1.body.status, 'Issued');
  assert.equal(made1.body.amount, 250);
  const seen = (await call('GET', '/api/me/penalties', { token: emp.token })).body.find((p) => p._id === made1.body._id);
  assert.equal(seen.reason, 'Repeated no helmet', 'the employee sees it, and can dispute it');
  assert.equal((await call('POST', `/api/penalties/${seen._id}/dispute`, { token: emp.token, body: { note: 'not me' } })).body.status, 'Disputed');

  const again = await call('POST', '/api/penalties', { token: sup.token, body: { employeeId: 'E007', violationIds: [made.body.ids[0]] } });
  assert.equal(again.status, 400, 'a violation already covered by a penalty cannot be penalised twice');
  assert.equal((await call('POST', '/api/penalties', { token: sup.token, body: { employeeId: 'E007' } })).status, 201, 'the remaining open violation can still be penalised');
});


test('each violation has a one-page PDF notice with the exact fault, for the supervisor and for the employee it belongs to', async () => {
  const sup = await login('S001', '123456789');
  const emp = await login('E008', '123456789');
  const other = await login('E009', '123456789');
  const made = await ingest(1);
  const id = made.body.ids[0];
  const pdf = async (url, token) => { const res = await fetch(base + url, { headers: { authorization: `Bearer ${token}` } }); return { status: res.status, type: res.headers.get('content-type'), head: Buffer.from(await res.arrayBuffer()).subarray(0, 5).toString() }; };

  const alert = await pdf(`/api/violations/${id}/notice.pdf`, sup.token);
  assert.equal(alert.status, 200);
  assert.equal(alert.type, 'application/pdf');
  assert.equal(alert.head, '%PDF-', 'the supervisor can open the notice even while it is only an alert');

  assert.equal((await pdf(`/api/me/violations/${id}/notice.pdf`, emp.token)).status, 404, 'an employee cannot open a case that is not confirmed or not theirs');
  await call('POST', `/api/violations/${id}/decision`, { token: sup.token, body: { decision: 'confirm', employeeId: emp.user.id } });
  const mine = await pdf(`/api/me/violations/${id}/notice.pdf`, emp.token);
  assert.equal(mine.status, 200);
  assert.equal(mine.head, '%PDF-');
  assert.equal((await pdf(`/api/me/violations/${id}/notice.pdf`, other.token)).status, 404, 'another employee cannot open it');
  assert.equal((await pdf(`/api/violations/${id}/notice.pdf`, emp.token)).status, 403, 'the supervisor route is closed to employees');
});
