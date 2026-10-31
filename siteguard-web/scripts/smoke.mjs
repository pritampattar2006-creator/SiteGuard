// Smoke test for the whole stack. Run with everything started (`npm run start:all`), then: `npm run smoke`
// It checks that every service answers, then walks one real case through: a photo is analysed, a worker is named in the name box,
// the case reaches the supervisor with a generated remark, the employee is alerted, and a second catch the same day is only counted.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const API = process.env.API_URL || 'http://localhost:4000';
const DETECTOR = process.env.DETECTOR_URL || 'http://localhost:5000';
const photo = process.argv[2] || path.resolve(here, '..', '..', 'ppe-detection', 'eval', 'cases', 'case_10.jpg');

let failed = 0;
const check = (ok, name, detail = '') => { console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `  (${detail})` : ''}`); if (!ok) failed += 1; };
const json = async (url, options = {}) => {
  const res = await fetch(url, options);
  return { status: res.status, body: await res.json().catch(() => ({})) };
};
const post = (url, body, headers = {}) => json(url, { method: 'POST', headers: { 'content-type': 'application/json', ...headers }, body: JSON.stringify(body) });

// 1. every service answers
for (const [name, url] of [['API', `${API}/api/health`], ['detector', `${DETECTOR}/health`], ['employee site', 'http://localhost:3001'], ['supervisor site', 'http://localhost:3002'], ['demo desk', 'http://localhost:3003']]) {
  try { const r = await fetch(url); check(r.ok, `${name} is up`); } catch { check(false, `${name} is up`, 'not reachable'); }
}

// 2. sign in and the roster
const sup = await post(`${API}/api/auth/login`, { employeeId: 'S001', password: '123456789' });
check(sup.status === 200, 'supervisor can sign in');
const auth = { authorization: `Bearer ${sup.body.token}` };
const team = (await json(`${API}/api/employees`, { headers: auth })).body;
check(Array.isArray(team) && team.length >= 60, 'dummy employees are loaded', `${team.length} employees`);
const target = team.find((e) => e.employeeId === 'E024') || team[0];

// 2b. sectors: each kind of work has its own required gear and its own supervisor
const sectors = (await json(`${API}/api/sectors/public`)).body;
const construction = sectors.find((x) => x.name === 'Civil Construction Site');
check(sectors.length >= 3 && Boolean(construction), 'the desk can list sectors with their required gear', sectors.map((x) => `${x.name}: ${x.requiredItems.join('+')}`).join(' | '));

// 3. a real picture through the detector (the desk sends the sector's gear and place), with a name typed in for worker 1
const image = fs.readFileSync(photo).toString('base64');
const body = { image, required: construction.requiredItems, sector: construction.id, location: construction.location, push: true, source: 'smoke', sourceName: path.basename(photo), assign: { 1: { employeeId: target.employeeId, name: target.name, jobRole: target.jobRole, department: target.department } } };
const first = await post(`${DETECTOR}/analyze`, body);
check(first.status === 200 && first.body.workers?.length > 0, 'photo analysed', `${first.body.workers?.length} workers`);
const w1 = first.body.workers?.find((w) => w.id === 1);
check(w1?.identity?.name === target.name, 'worker 1 carries the typed name', w1?.identity?.name);
check(first.body.workers?.every((w) => typeof w.label === 'string' && w.label.length > 0), 'every worker has a label (a name, or Employee N when nobody could be told)');
check(first.body.pushed + first.body.repeats > 0, 'caught people were sent to the supervisor', `${first.body.pushed} new, ${first.body.repeats} repeat`);

// 4. one violation per person per day
const second = await post(`${DETECTOR}/analyze`, body);
check(second.body.pushed === 0, 'a second catch the same day creates no new case', `${second.body.repeats} counted as repeats`);

// 5. the supervisor sees the case with a remark; the employee is alerted
const queue = (await json(`${API}/api/review/queue`, { headers: auth })).body;
const mine = queue.find((q) => q.suggested?.employeeId === target.employeeId);
check(Boolean(mine), `${target.name}'s case is in the review queue`);
check(/was seen without/.test(mine?.remarks || ''), 'the case has a generated remark', (mine?.remarks || '').slice(0, 70));
const emp = await post(`${API}/api/auth/login`, { employeeId: target.employeeId, password: '123456789' });
const notes = (await json(`${API}/api/notifications`, { headers: { authorization: `Bearer ${emp.body.token}` } })).body;
check(notes.some((n) => /Safety alert/.test(n.message)), 'the employee received a safety alert');

// 5b. only the supervisor of that sector (and the head supervisor) sees the case
const wire = await post(`${API}/api/auth/login`, { employeeId: 'S002', password: '123456789' });
const wireQueue = (await json(`${API}/api/review/queue`, { headers: { authorization: `Bearer ${wire.body.token}` } })).body;
check(!wireQueue.some((q) => q.suggested?.employeeId === target.employeeId), "the wireman supervisor does not see a construction case", `${wireQueue.length} wireman cases`);
check(mine?.sectorName === 'Civil Construction Site', 'the case is tagged with its sector', mine?.sectorName);
check(Boolean(mine?.contextPath) && mine.contextPath !== mine.evidencePath, 'the case has a close-up of the worker and the whole picture');

// 6. salary view for the employee
const salary = (await json(`${API}/api/me/salary`, { headers: { authorization: `Bearer ${emp.body.token}` } })).body;
check(salary.monthlySalary > 0 && salary.payslips?.length === 6, 'the employee can see salary and pay history', `₹${salary.monthlySalary}`);

console.log(failed ? `\n${failed} check(s) failed.` : '\nAll checks passed.');
process.exit(failed ? 1 : 0);
