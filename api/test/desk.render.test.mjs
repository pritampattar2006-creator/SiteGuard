// Renders the demo desk's result components with sample data, to catch runtime errors that compiling alone would not.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..', '..');
const require = createRequire(import.meta.url);
const esbuild = require(path.join(root, 'node_modules', 'esbuild'));
const React = require(path.join(root, 'node_modules', 'react'));
const { renderToString } = require(path.join(root, 'node_modules', 'react-dom', 'server'));

globalThis.window = { location: { hostname: 'localhost' } };
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };

async function load() {
  const out = path.join(here, '.desk.bundle.mjs');
  await esbuild.build({
    entryPoints: [path.join(root, 'shared', 'detect.jsx')], outfile: out, bundle: true, format: 'esm', platform: 'node', jsx: 'automatic',
    external: ['react', 'react-dom', 'react-router-dom', 'react/jsx-runtime'], define: { 'import.meta.env.VITE_DETECTOR_URL': 'undefined', 'import.meta.env.VITE_API_URL': 'undefined' }, logLevel: 'silent',
  });
  return import(pathToFileURL(out).href);
}

const workers = [
  { id: 1, label: 'Employee 1', status: 'VIOLATION', missing: ['NO HELMET'], identity: null },
  { id: 2, label: 'Aarav Bhat', status: 'VIOLATION', missing: ['NO VEST'], identity: { employeeId: 'E024', name: 'Aarav Bhat', jobRole: 'Carpenter', dummy: true } },
  { id: 3, label: 'Employee 3', status: 'COMPLIANT', missing: [], identity: null },
];

test('the result table shows "Employee N", names and verdicts', async () => {
  const { WorkersTable } = await load();
  const html = renderToString(React.createElement(WorkersTable, { workers }));
  assert.match(html, /Employee 1/);
  assert.match(html, /Aarav Bhat/);
  assert.ok(!/Type or pick a name/.test(html), 'there is no manual name box any more');
});

test('the scene summary renders the counts and who is not wearing gear', async () => {
  const { Scene } = await load();
  const html = renderToString(React.createElement(Scene, { workers })).replace(/<!-- -->/g, '');
  assert.match(html, /of 3 fully equipped/);
  assert.match(html, /Not wearing gear right now/);
});
