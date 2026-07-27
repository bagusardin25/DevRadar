import { execSync } from 'child_process';
import { build } from 'esbuild';
import { cpSync, mkdirSync, rmSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const isFirefox = process.argv.includes('--firefox');
const isWatch = process.argv.includes('--watch');
const outDir = resolve(__dirname, isFirefox ? 'dist-firefox' : 'dist');

if (existsSync(outDir)) rmSync(outDir, { recursive: true });
mkdirSync(outDir, { recursive: true });

// 1. Build side panel SPA with Vite
console.log('[build] Side panel (Vite + React)...');
execSync(`npx vite build`, { cwd: __dirname, stdio: 'inherit' });

// 2. Bundle content script (IIFE)
console.log('[build] Content script (esbuild)...');
await build({
  entryPoints: [resolve(__dirname, 'src/content/index.ts')],
  bundle: true,
  format: 'iife',
  target: 'es2022',
  outfile: resolve(outDir, 'content.js'),
  minify: !isWatch,
});

// 3. Bundle background service worker (IIFE)
console.log('[build] Background worker (esbuild)...');
await build({
  entryPoints: [resolve(__dirname, 'src/background/index.ts')],
  bundle: true,
  format: 'iife',
  target: 'es2022',
  outfile: resolve(outDir, 'background.js'),
  minify: !isWatch,
});

// 4. Copy manifest
const manifestSrc = resolve(
  __dirname,
  isFirefox ? 'manifest.firefox.json' : 'manifest.json',
);
cpSync(manifestSrc, resolve(outDir, 'manifest.json'));

// 5. Copy icons
const iconsDir = resolve(__dirname, 'public/icons');
if (existsSync(iconsDir)) {
  cpSync(iconsDir, resolve(outDir, 'icons'), { recursive: true });
}

console.log(`[build] Done → ${outDir}`);
