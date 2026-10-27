// json-observer-v2: detach and encode each bounded observation before the next call.
const fs = require('node:fs');
const {pathToFileURL} = require('node:url');
const emit = process.stdout.write.bind(process.stdout);
const stringify = JSON.stringify;
const byteLength = Buffer.byteLength;
console.log = (...args) => console.error(...args);

function snapshot(value) {
  const ancestors = new Set();
  let budget = 0;
  function account(bytes) {
    budget += bytes;
    if (budget > 16384) throw RangeError('JSON observation exceeds 16 KiB');
  }
  function copy(v, depth) {
    if (depth > 8) throw RangeError('JSON observation nesting exceeds eight levels');
    if (v === null || typeof v === 'boolean') { account(v === null ? 4 : v ? 4 : 5); return v; }
    if (typeof v === 'string') { account(2 + byteLength(v, 'utf8')); return v; }
    if (typeof v === 'number' && Number.isFinite(v)) { account(String(v).length); return v; }
    const array = Array.isArray(v);
    if (typeof v !== 'object' || (!array && Object.getPrototypeOf(v) !== Object.prototype))
      throw TypeError('Unsupported JSON observation');
    if (ancestors.has(v)) throw TypeError('Cyclic JSON observation');
    // Serialization hooks are code, not supported JSON data; never invoke or coerce them.
    const hook = Object.getOwnPropertyDescriptor(v, 'toJSON');
    if ((hook && (!('value' in hook) || typeof hook.value === 'function')) ||
        (!hook && typeof v.toJSON === 'function')) throw TypeError('Unsupported JSON hook');
    const keys = array ? null : Object.keys(v);
    const length = array ? v.length : keys.length;
    if (!Number.isInteger(length) || length < 0 || length > 256)
      throw RangeError('JSON collection exceeds 256 items');
    account(2 + Math.max(0, length - 1));
    ancestors.add(v);
    try {
      if (array) {
        const result = [];
        // Only our new copy is modified. Candidate arrays/objects remain untouched.
        Object.defineProperty(result, 'toJSON', {value: null});
        for (let i = 0; i < length; i++) {
          if (!Object.hasOwn(v, i)) throw TypeError('Sparse arrays are not JSON observations');
          result.push(copy(v[i], depth + 1));
        }
        return result;
      }
      const result = Object.create(null);
      for (const key of keys) {
        account(3 + byteLength(key, 'utf8'));
        result[key] = copy(v[key], depth + 1);
      }
      return result;
    } finally { ancestors.delete(v); }
  }
  const encoded = stringify(copy(value, 0));
  if (typeof encoded !== 'string' || byteLength(encoded, 'utf8') > 16384)
    throw RangeError('Encoded JSON observation exceeds 16 KiB');
  return encoded;
}

async function main() {
  const inputs = JSON.parse(fs.readFileSync('/verifier/inputs.json', 'utf8'));
  const observations = [];
  for (const call of inputs.calls) {
    try {
      let fn = inputs.module.endsWith('.mjs')
        ? await import(pathToFileURL(inputs.module).href)
        : require(inputs.module);
      for (const name of inputs.export ? inputs.export.split('.') : []) fn = fn[name];
      const value = snapshot(await fn(...call.args));
      // Retain immutable JSON text, never a candidate-owned reference or deferred serializer.
      observations.push('{"id":' + stringify(call.id) + ',"kind":"value","value":' + value + '}');
    } catch (error) {
      let name = 'Error';
      try { if (typeof error?.name === 'string') name = error.name.slice(0, 200); } catch {}
      observations.push('{"id":' + stringify(call.id) + ',"kind":"execution_error","error":' + stringify(name) + '}');
    }
  }
  emit('{"version":"observations-v1","observations":[' + observations.join(',') + ']}\n');
}
main().catch(() => process.exitCode = 2);
