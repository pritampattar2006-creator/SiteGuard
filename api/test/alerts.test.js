import assert from 'node:assert/strict';
import { test } from 'node:test';
import { newAlertState, planAlerts, sceneSummary } from '../../shared/alerts.js';

const raju = { id: 1, status: 'VIOLATION', missing: ['NO HELMET'], identity: { employeeId: 'D005', name: 'Raju Patil' } };
const anil = { id: 2, status: 'VIOLATION', missing: ['NO HELMET', 'NO VEST'], identity: { employeeId: 'D006', name: 'Anil Naik' } };
const ok = { id: 3, status: 'COMPLIANT', missing: [] };
const MIN = 60 * 1000;

test('a named worker is spoken to by first name, and only once per 10 minutes', () => {
  const first = planAlerts([raju], 'Gate 2', newAlertState(), 0);
  assert.deepEqual(first.speak, ['Raju, please wear your helmet.']);
  assert.equal(planAlerts([raju], 'Gate 2', first.state, 5 * MIN).speak.length, 0, 'still inside the 10 minutes');
  assert.equal(planAlerts([raju], 'Gate 2', first.state, 11 * MIN).speak.length, 1, 'after 10 minutes he is told again');
});

test('several missing items are read out naturally', () => {
  assert.equal(planAlerts([anil], '', newAlertState(), 0).speak[0], 'Anil, please wear your helmet and vest.');
});

test('many people caught at once are each spoken to by name; there is never an announcement to everyone', () => {
  const crowd = [raju, anil, { id: 4, status: 'VIOLATION', missing: ['NO VEST'], label: 'Employee 4' }, { id: 5, status: 'VIOLATION', missing: ['NO HELMET'], label: 'Employee 5' }];
  const plan = planAlerts(crowd, 'Gate 2', newAlertState(), 0);
  assert.equal(plan.speak.length, 4);
  assert.ok(!plan.speak.some((s) => /everyone/i.test(s)));
  assert.deepEqual(plan.speak.slice(0, 2), ['Raju, please wear your helmet.', 'Anil, please wear your helmet and vest.']);
});

test('compliant workers and "needs review" never trigger a spoken alert', () => {
  assert.equal(planAlerts([ok, { id: 9, status: 'NEEDS_REVIEW', missing: ['NO HELMET'] }], '', newAlertState(), 0).speak.length, 0);
});

test('an unnamed worker is announced by place, and not repeated for the same place and gear', () => {
  const stranger = { id: 7, status: 'VIOLATION', missing: ['NO HELMET'] };
  const first = planAlerts([stranger], 'Crane bay', newAlertState(), 0);
  assert.equal(first.speak[0], 'Attention at Crane bay: a worker is not wearing a helmet.');
  assert.equal(planAlerts([stranger], 'Crane bay', first.state, 2 * MIN).speak.length, 0);
});

test('the scene summary says who is not wearing gear right now', () => {
  const s = sceneSummary([ok, ok, raju, anil]);
  assert.deepEqual([s.total, s.ok, s.caught, s.helmetsMissing, s.vestsMissing], [4, 2, 2, 2, 1]);
  assert.deepEqual(s.notWearing[0], { label: 'Raju Patil', items: ['helmet'] });
});
