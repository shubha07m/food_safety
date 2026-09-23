// Build an isolated static deployment using only the Node standard library.
import { cpSync, existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';

export function buildDeployment(root, env = process.env) {
  const source = resolve(root, 'site');
  const config = JSON.parse(readFileSync(join(source, 'maps-config.json'), 'utf8'));
  if (Object.keys(config).length !== 1 || config.browser_key !== '') {
    throw new Error('Source browser configuration must be blank');
  }
  const key = (env.GOOGLE_MAPS_BROWSER_KEY || '').trim();
  if (key && !/^AIza[A-Za-z0-9_-]{35}$/.test(key)) throw new Error('Invalid browser configuration format');
  const privateValues = [env.GOOGLE_MAPS_API_KEY, env.GEMINI_API_KEY].filter(Boolean);
  if (key && privateValues.includes(key)) throw new Error('Browser configuration must use a separate value');
  if (env.REQUIRE_BROWSER_MAP_CONFIG === 'true' && !key) throw new Error('Browser configuration is required for this deployment');

  // Check all bytes before copying; never echo a matching value or provider payload.
  function checkTree(path, inspectContent = false) {
    if (lstatSync(path).isSymbolicLink()) throw new Error('Deployment input cannot contain symbolic links');
    if (lstatSync(path).isDirectory()) {
      for (const name of readdirSync(path)) checkTree(join(path, name), inspectContent);
    } else if (inspectContent) {
      const body = readFileSync(path);
      if (privateValues.some(value => body.includes(Buffer.from(value))) ||
          /AIza[A-Za-z0-9_-]{35}|github_pat_[A-Za-z0-9_]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|BEGIN [A-Z ]*PRIVATE KEY/.test(body.toString('utf8'))) {
        throw new Error('Unexpected value in deployment source');
      }
    }
  }
  checkTree(source, true);
  const destination = resolve(root, 'dist');
  if (existsSync(destination)) throw new Error('Deployment directory already exists; use a fresh workspace');
  const wrangler = JSON.parse(readFileSync(resolve(root, 'wrangler.jsonc'), 'utf8'));
  if (wrangler.assets?.directory !== './site') throw new Error('Unexpected static asset directory');
  if (wrangler.main) {
    if (wrangler.main !== 'worker/visits.mjs') throw new Error('Unexpected worker entry');
    checkTree(resolve(root, 'worker'), true);
  }
  mkdirSync(destination);
  cpSync(source, join(destination, 'site'), { recursive: true });
  if (wrangler.main) cpSync(resolve(root, 'worker'), join(destination, 'worker'), { recursive: true });
  writeFileSync(join(destination, 'site/maps-config.json'), JSON.stringify({ browser_key: key }, null, 2) + '\n');
  writeFileSync(join(destination, 'wrangler.json'), JSON.stringify(wrangler, null, 2) + '\n');
  return destination;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try {
    buildDeployment(resolve(import.meta.dirname, '..'));
    console.log('Static deployment artifact prepared in dist/');
  } catch {
    console.error('Deployment artifact generation failed; check source configuration, environment, and a fresh dist directory.');
    process.exitCode = 1;
  }
}
