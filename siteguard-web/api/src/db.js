// Embedded, MongoDB-compatible document store (NeDB). It has the same query and update style as MongoDB, needs no server,
// and keeps each collection in a file. To use a real MongoDB later, only this file needs to change.
import Datastore from '@seald-io/nedb';
import fs from 'node:fs';
import path from 'node:path';

export async function openDb(dir) {
  if (dir) fs.mkdirSync(dir, { recursive: true });
  const make = (name) => (dir ? new Datastore({ filename: path.join(dir, `${name}.db`) }) : new Datastore({ inMemoryOnly: true }));
  const db = { users: make('users'), violations: make('violations'), penalties: make('penalties'), notifications: make('notifications'), sectors: make('sectors'), accidents: make('accidents') };
  await Promise.all(Object.values(db).map((collection) => collection.loadDatabaseAsync()));
  return db;
}
