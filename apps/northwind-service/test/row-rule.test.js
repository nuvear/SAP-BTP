// Proves the row rule: same request, different users, different rows.
// Run with:  npm test     (starts the service on port 4044 with the in-memory database)
const { test, before, after } = require('node:test');
const assert = require('node:assert');
const { spawn } = require('node:child_process');

const BASE = 'http://localhost:4044/odata/v4/northwind';
let server;

const get = async (user, path) => {
  const headers = user ? { Authorization: 'Basic ' + Buffer.from(`${user}:${user}`).toString('base64') } : {};
  const res = await fetch(`${BASE}/${path}`, { headers });
  return { status: res.status, body: res.status === 200 ? await res.json() : null };
};

before(async () => {
  // Start node directly, not through npx, so that server.kill() really stops the service.
  server = spawn(process.execPath, [require.resolve('@sap/cds/bin/serve.js'), '--port', '4044'], { cwd: __dirname + '/..', stdio: 'pipe' });
  await new Promise((resolve, reject) => {
    server.stdout.on('data', d => String(d).includes('server listening') && resolve());
    server.on('exit', code => reject(new Error('service exited: ' + code)));
  });
});
after(() => server.kill());

test('a request without a user is rejected', async () => {
  assert.strictEqual((await get(null, 'Orders?$top=1')).status, 401);
});

test('a user without a sales role is forbidden', async () => {
  assert.strictEqual((await get('guest', 'Orders?$top=1')).status, 403);
});

test('head office (nancy) sees all 830 orders', async () => {
  const r = await get('nancy', 'Orders?$count=true&$top=0');
  assert.strictEqual(r.body['@odata.count'], 830);
});

test('the London office (steven) sees only the 224 orders of UK salespeople', async () => {
  const r = await get('steven', 'Orders?$count=true&$top=0');
  assert.strictEqual(r.body['@odata.count'], 224);
});

test('order 11070 belongs to a USA salesperson: nancy reads it, steven gets 404', async () => {
  assert.strictEqual((await get('nancy', 'Orders(11070)')).status, 200);
  assert.strictEqual((await get('steven', 'Orders(11070)')).status, 404);   // not 403: existence is not revealed
});

test('the rule also covers order lines, by both access paths', async () => {
  assert.strictEqual((await get('steven', 'Orders(11070)/details')).status, 404);           // the parent order is hidden, so is the path
  assert.strictEqual((await get('steven', 'OrderDetails?$filter=order_OrderID eq 11070')).body.value.length, 0);
  assert.strictEqual((await get('nancy', 'OrderDetails?$filter=order_OrderID eq 11070')).body.value.length, 4);
});

test('order 11019 belongs to a UK salesperson: both users read it', async () => {
  for (const u of ['nancy', 'steven']) assert.strictEqual((await get(u, 'Orders(11019)')).status, 200);
});

test('dates are shifted by 28 years', async () => {
  const o = (await get('nancy', 'Orders(10248)')).body;
  assert.strictEqual(o.OrderDate, '2024-07-04');
});

test('the service is read-only', async () => {
  const res = await fetch(`${BASE}/Orders(11019)`, { method: 'PATCH',
    headers: { 'Content-Type': 'application/json', Authorization: 'Basic ' + Buffer.from('nancy:nancy').toString('base64') },
    body: JSON.stringify({ Freight: 1 }) });
  assert.strictEqual(res.status, 405);
});
