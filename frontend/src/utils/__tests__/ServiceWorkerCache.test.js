const fs = require('fs');
const os = require('os');
const path = require('path');

const { computeBuildId, stampServiceWorker } = require('../../../scripts/stamp-sw-version');

describe('BS-10C Service Worker automatic cache versioning & lifecycle', () => {
  test('stampServiceWorker stamps deterministic CACHE_NAME from asset-manifest.json and changes across builds', () => {
    const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bopsocial-sw-'));
    const swTemplate = fs.readFileSync(
      path.resolve(__dirname, '../../../public/sw.js'),
      'utf8',
    );

    fs.writeFileSync(path.join(tmpDir, 'sw.js'), swTemplate, 'utf8');
    fs.writeFileSync(
      path.join(tmpDir, 'asset-manifest.json'),
      JSON.stringify({ files: { 'main.js': '/static/js/main.aaa111.js' } }),
      'utf8',
    );
    const cacheA = stampServiceWorker(tmpDir);
    const stampedA = fs.readFileSync(path.join(tmpDir, 'sw.js'), 'utf8');
    expect(cacheA).toBe(`bopsocial-${computeBuildId(JSON.stringify({ files: { 'main.js': '/static/js/main.aaa111.js' } }))}`);
    expect(stampedA).toContain(`const CACHE_NAME = '${cacheA}';`);

    fs.writeFileSync(path.join(tmpDir, 'sw.js'), swTemplate, 'utf8');
    fs.writeFileSync(
      path.join(tmpDir, 'asset-manifest.json'),
      JSON.stringify({ files: { 'main.js': '/static/js/main.bbb222.js' } }),
      'utf8',
    );
    const cacheB = stampServiceWorker(tmpDir);
    expect(cacheB).not.toBe(cacheA);

    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  test('sw.js skips API, media, Authorization headers, and hashed JS/CSS chunks, and purges old caches on activate', async () => {
    const swSource = fs.readFileSync(
      path.resolve(__dirname, '../../../public/sw.js'),
      'utf8',
    );
    const listeners = {};
    const deletedCaches = [];
    const openedCaches = [];

    const mockCaches = {
      keys: jest.fn().mockResolvedValue(['bopsocial-v2.6b.2.1', 'bopsocial-oldbuild', 'bopsocial-__BUILD_ID__']),
      delete: jest.fn((k) => {
        deletedCaches.push(k);
        return Promise.resolve(true);
      }),
      open: jest.fn((name) => {
        openedCaches.push(name);
        return Promise.resolve({ addAll: jest.fn().mockResolvedValue(undefined) });
      }),
      match: jest.fn().mockResolvedValue(undefined),
    };

    const mockSelf = {
      addEventListener: (type, fn) => {
        listeners[type] = fn;
      },
      skipWaiting: jest.fn(),
      clients: { claim: jest.fn() },
    };

    const runner = new Function('self', 'caches', 'fetch', swSource);
    runner(mockSelf, mockCaches, jest.fn());

    // Activate purges all obsolete caches
    let activatePromise;
    listeners.activate({ waitUntil: (p) => { activatePromise = p; } });
    await activatePromise;
    expect(deletedCaches).toEqual(['bopsocial-v2.6b.2.1', 'bopsocial-oldbuild']);
    expect(mockSelf.clients.claim).toHaveBeenCalled();

    // Fetch skips /api/, /media/, /static/js/, /static/css/, and Authorization header
    const skipUrls = [
      'http://localhost:3010/api/ai/hashtags/',
      'http://localhost:3010/media/profile_images/Bop_Agencia.png',
      'http://localhost:3010/static/js/main.1234.js',
      'http://localhost:3010/static/css/main.1234.css',
    ];
    for (const url of skipUrls) {
      const respondWith = jest.fn();
      listeners.fetch({
        request: { method: 'GET', url, mode: 'cors', headers: { get: () => null } },
        respondWith,
      });
      expect(respondWith).not.toHaveBeenCalled();
    }

    const authRespondWith = jest.fn();
    listeners.fetch({
      request: { method: 'GET', url: 'http://localhost:3010/', mode: 'navigate', headers: { get: (h) => (h === 'Authorization' ? 'Bearer xyz' : null) } },
      respondWith: authRespondWith,
    });
    expect(authRespondWith).not.toHaveBeenCalled();
  });
});
