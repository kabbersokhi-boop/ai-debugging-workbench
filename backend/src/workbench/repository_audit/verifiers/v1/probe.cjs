// Fixed adapter; expected values and scoring never enter the candidate environment.
const fs = require('node:fs');
const {pathToFileURL} = require('node:url');
const emit = process.stdout.write.bind(process.stdout);
console.log = (...args) => console.error(...args);
async function main() {
  const inputs = JSON.parse(fs.readFileSync('/verifier/inputs.json', 'utf8'));
  const observations = [];
  for (const call of inputs.calls) {
    try {
      let fn = inputs.module.endsWith('.mjs')
        ? await import(pathToFileURL(inputs.module).href)
        : require(inputs.module);
      for (const name of inputs.export ? inputs.export.split('.') : []) fn = fn[name];
      const value = await fn(...call.args);
      // JSON.stringify silently rewrites undefined/NaN; reject that unsupported domain.
      function valid(v) {
        if (v === null || typeof v === 'string' || typeof v === 'boolean') return;
        if (typeof v === 'number' && Number.isFinite(v)) return;
        if (Array.isArray(v)) return v.forEach(valid);
        if (typeof v === 'object' && Object.getPrototypeOf(v) === Object.prototype)
          return Object.values(v).forEach(valid);
        throw Error('Unsupported JSON observation');
      }
      valid(value);
      observations.push({id: call.id, kind: 'value', value});
    } catch (error) {
      observations.push({id: call.id, kind: 'execution_error', error: String(error.name)});
    }
  }
  emit(JSON.stringify({version: 'observations-v1', observations}) + '\n');
}
main().catch(() => process.exitCode = 2);
