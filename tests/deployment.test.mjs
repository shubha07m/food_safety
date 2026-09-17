import assert from 'node:assert/strict';
import test from 'node:test';
import { mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { buildDeployment } from '../scripts/build_deployment.mjs';

function fixture(t) {
  const root = mkdtempSync(join(tmpdir(), 'food-deployment-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  mkdirSync(join(root, 'site'));
  writeFileSync(join(root, 'site/maps-config.json'), '{"browser_key":""}\n');
  writeFileSync(join(root, 'site/index.html'), '<h1>Puja FoodPath</h1>');
  writeFileSync(join(root, 'wrangler.jsonc'), '{"name":"fixture","assets":{"directory":"./site"}}');
  writeFileSync(join(root, '.gitignore'), 'dist/\n');
  execFileSync('git', ['init', '-q'], { cwd: root });
  execFileSync('git', ['add', '.'], { cwd: root });
  return root;
}

for (const configured of [false, true]) {
  test(`isolated artifact ${configured ? 'configured' : 'keyless'} leaves index/source unchanged`, t => {
    const root = fixture(t);
    const key = configured ? 'AIza' + 'd'.repeat(35) : '';
    const before = execFileSync('git', ['diff', '--cached', '--binary'], { cwd: root });
    const status = execFileSync('git', ['status', '--porcelain'], { cwd: root });
    buildDeployment(root, { GOOGLE_MAPS_BROWSER_KEY: key });
    assert.deepEqual(JSON.parse(readFileSync(join(root, 'dist/site/maps-config.json'))), { browser_key: key });
    assert.deepEqual(JSON.parse(readFileSync(join(root, 'site/maps-config.json'))), { browser_key: '' });
    assert.deepEqual(execFileSync('git', ['diff', '--cached', '--binary'], { cwd: root }), before);
    assert.deepEqual(execFileSync('git', ['status', '--porcelain'], { cwd: root }), status);
    assert.equal(JSON.parse(readFileSync(join(root, 'dist/wrangler.json'))).assets.directory, './site');
    assert.throws(() => buildDeployment(root, {}), /already exists/);
  });
}

test('populated source cannot be packaged', t => {
  const root = fixture(t);
  writeFileSync(join(root, 'site/maps-config.json'), '{"browser_key":"not-empty"}');
  assert.throws(() => buildDeployment(root, {}), /must be blank/);
  assert.equal(existsSync(join(root, 'dist')), false);
});

for (const name of ['GOOGLE_MAPS_API_KEY', 'GEMINI_API_KEY']) {
  test(`${name} is never a fallback and cannot be reused or copied`, t => {
    const root = fixture(t);
    const value = 'AIza' + 'e'.repeat(35);
    assert.throws(() => buildDeployment(root, { GOOGLE_MAPS_BROWSER_KEY: value, [name]: value }), /separate/);
    writeFileSync(join(root, 'site/extra.txt'), 'private-fixture');
    assert.throws(() => buildDeployment(root, { [name]: 'private-fixture' }), /Unexpected value/);
    rmSync(join(root, 'site/extra.txt'));
    buildDeployment(root, { [name]: value });
    assert.deepEqual(JSON.parse(readFileSync(join(root, 'dist/site/maps-config.json'))), { browser_key: '' });
  });
}

test('deployment can require explicit configuration without dotenv', t => {
  const root = fixture(t);
  writeFileSync(join(root, '.env'), 'GOOGLE_MAPS_BROWSER_KEY=fixture');
  assert.throws(() => buildDeployment(root, { REQUIRE_BROWSER_MAP_CONFIG: 'true' }), /required/);
  assert.throws(() => buildDeployment(root, { GOOGLE_MAPS_BROWSER_KEY: 'invalid' }), /format/);
});
