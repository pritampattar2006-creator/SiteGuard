import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createApp } from './app.js';
import { openDb } from './db.js';
import { loadPolicy } from './policy.js';
import { backfillSectors, renameSectors, seedAccounts, setEmployeePasswords, setPresentSupervisorPasswords, settlePendingSupervisors } from './seed.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const port = Number(process.env.PORT || 4000);

// Secrets come from the environment. If they are not set, safe random values are used for this run only.
const secret = process.env.SITEGUARD_SECRET || crypto.randomBytes(32).toString('hex');
if (!process.env.SITEGUARD_SECRET) console.warn('SITEGUARD_SECRET is not set: using a random one, so everyone is signed out when the API restarts.');
const ingestKey = process.env.INGEST_KEY || 'dev-ingest-key';
if (!process.env.INGEST_KEY) console.warn("INGEST_KEY is not set: using the development key 'dev-ingest-key'. Set INGEST_KEY before any real use.");

const db = await openDb(process.env.DATA_DIR || path.join(root, 'data'));
await seedAccounts(db);
const renamedSectors = await renameSectors(db);
if (renamedSectors) console.log(`${renamedSectors} sector(s) renamed to their professional names.`);
await backfillSectors(db);
const switchedSupervisors = await setPresentSupervisorPasswords(db);
if (switchedSupervisors) console.log(`The ${switchedSupervisors} supervisor accounts that exist now use the shared password.`);
const settled = await settlePendingSupervisors(db);
if (settled) console.log(`${settled} waiting sign-up request(s) were approved and given the shared password.`);
const switched = await setEmployeePasswords(db);
if (switched) console.log(`Every employee account (${switched}) now uses the one employee password.`);
const app = createApp({ db, policy: loadPolicy(path.join(root, 'config', 'policy.json')), secret, ingestKey, uploadsDir: process.env.UPLOADS_DIR || path.join(root, 'uploads'), demoMode: process.env.DEMO_MODE !== '0' });
app.listen(port, () => console.log(`SiteGuard API on http://localhost:${port}  (employee site :3001, supervisor site :3002)`));
