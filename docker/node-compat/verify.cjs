'use strict';
// Trusted build check: read bytes only, never import the vendored dependency.
const fs = require('node:fs');
const crypto = require('node:crypto');
const manifest = JSON.parse(fs.readFileSync('/opt/node-compat/manifest.json', 'utf8'));
const root = '/opt/test-tools/node_modules/array-flatten/';
const names = fs.readdirSync(root).sort();
if (JSON.stringify(names) !== JSON.stringify(Object.keys(manifest.files).sort())) throw Error('Capsule files differ');
for (const [name, expected] of Object.entries(manifest.files)) {
  if (!/^[A-Za-z0-9.-]+$/.test(name)) throw Error('Unsafe capsule name');
  const actual = crypto.createHash('sha256').update(fs.readFileSync(root + name)).digest('hex');
  if (actual !== expected) throw Error('Capsule byte mismatch: ' + name);
}
