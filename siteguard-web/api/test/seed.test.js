import assert from 'node:assert/strict';
import { test } from 'node:test';
import { openDb } from '../src/db.js';
import { renameSectors, seedAccounts } from '../src/seed.js';

test('seeding that was cut short part-way starts over, and a finished seeding is left alone', async () => {
  const db = await openDb(null);
  await db.users.insertAsync({ employeeId: 'S001', role: 'supervisor', name: 'half-done' }); // as if the process stopped mid-seed
  assert.equal(await seedAccounts(db), true);
  assert.ok((await db.users.countAsync({ role: 'employee' })) >= 100, 'all the dummy employees are there');
  assert.equal(await db.sectors.countAsync({}), 3);
  assert.equal(await db.users.countAsync({ employeeId: 'S001' }), 1, 'no duplicate of the half-done account');
  assert.equal(await seedAccounts(db), false, 'a second call does nothing');
});

test('accounts are never wiped once real cases exist', async () => {
  const db = await openDb(null);
  await db.users.insertAsync({ employeeId: 'E900', role: 'employee', name: 'real person' });
  await db.violations.insertAsync({ number: 1, status: 'Pending review' });
  assert.equal(await seedAccounts(db), false);
  assert.equal(await db.users.countAsync({ employeeId: 'E900' }), 1);
});


test('sectors made with the old names are renamed once to professional names, along with what carries those names', async () => {
  const db = await openDb(null);
  await db.sectors.insertAsync({ name: 'Wireman', location: 'Wiring block' });
  await db.sectors.insertAsync({ name: 'Welding', location: 'Welding' });
  await db.users.insertAsync({ employeeId: 'S002', role: 'supervisor', department: 'Wireman' });
  await db.users.insertAsync({ employeeId: 'BWA101', role: 'employee', department: 'wwelding' }); // the typo
  await db.violations.insertAsync({ number: 1, sectorName: 'Wireman' });
  await db.accidents.insertAsync({ number: 1, sectorName: 'Welding', venue: 'Welding \u00b7 Bay 2' });
  assert.equal(await renameSectors(db), 2);
  assert.ok(await db.sectors.findOneAsync({ name: 'Electrical Wiring Works', location: 'Wiring block' }));
  assert.ok(await db.sectors.findOneAsync({ name: 'Fabrication & Welding Bay', location: 'Fabrication bay' }));
  assert.equal((await db.users.findOneAsync({ employeeId: 'S002' })).department, 'Electrical Wiring Works');
  assert.equal((await db.users.findOneAsync({ employeeId: 'BWA101' })).department, 'Fabrication & Welding Bay', 'the typo is fixed too');
  assert.equal((await db.violations.findOneAsync({ number: 1 })).sectorName, 'Electrical Wiring Works');
  const accident = await db.accidents.findOneAsync({ number: 1 });
  assert.equal(accident.sectorName, 'Fabrication & Welding Bay');
  assert.equal(accident.venue, 'Fabrication & Welding Bay \u00b7 Bay 2');
  assert.equal(await renameSectors(db), 0, 'a second run changes nothing');
});

test('a professional name that is already taken is never overwritten', async () => {
  const db = await openDb(null);
  await db.sectors.insertAsync({ name: 'Wireman' });
  await db.sectors.insertAsync({ name: 'Electrical Wiring Works' });
  assert.equal(await renameSectors(db), 0);
  assert.equal(await db.sectors.countAsync({}), 2);
});
