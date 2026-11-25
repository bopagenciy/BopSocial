const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

function computeBuildId(manifestContent) {
  return crypto.createHash('sha256').update(manifestContent, 'utf8').digest('hex').slice(0, 12);
}

function stampServiceWorker(buildDir) {
  const manifestPath = path.join(buildDir, 'asset-manifest.json');
  const swPath = path.join(buildDir, 'sw.js');

  if (!fs.existsSync(manifestPath)) {
    throw new Error(`asset-manifest.json not found at ${manifestPath}`);
  }
  if (!fs.existsSync(swPath)) {
    throw new Error(`sw.js not found at ${swPath}`);
  }

  const manifestContent = fs.readFileSync(manifestPath, 'utf8');
  const buildId = computeBuildId(manifestContent);
  const cacheName = `bopsocial-${buildId}`;

  const swSource = fs.readFileSync(swPath, 'utf8');
  const updated = swSource.replace(
    /const CACHE_NAME = ['"][^'"]+['"];/,
    `const CACHE_NAME = '${cacheName}';`
  );

  if (updated === swSource && !swSource.includes(cacheName)) {
    throw new Error('Failed to stamp CACHE_NAME in build/sw.js');
  }

  fs.writeFileSync(swPath, updated, 'utf8');
  return cacheName;
}

if (require.main === module) {
  const buildDir = path.resolve(__dirname, '..', 'build');
  const cacheName = stampServiceWorker(buildDir);
  console.log(`Stamped build/sw.js with CACHE_NAME=${cacheName}`);
}

module.exports = { computeBuildId, stampServiceWorker };
