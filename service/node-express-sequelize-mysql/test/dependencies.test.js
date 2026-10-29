const assert = require('node:assert/strict');
const { test } = require('node:test');
const express = require('express');
const bodyParser = require('body-parser');

process.env.DATABASE_URL = 'mysql://root:password@localhost/test';

test('upgraded Express, Joi and Sequelize initialize and validate requests', async (t) => {
  const app = express();
  app.use(bodyParser.json());
  app.use(require('../src/handler'));
  app.use(require('../src/middleware/error-handler'));
  const server = app.listen(0, '127.0.0.1');
  await new Promise((resolve) => server.once('listening', resolve));
  t.after(() => new Promise((resolve) => server.close(resolve)));
  const url = `http://127.0.0.1:${server.address().port}`;
  const health = await fetch(`${url}/healthcheck`, { method: 'HEAD' });
  assert.equal(health.status, 204);
  const invalid = await fetch(`${url}/api/accounts`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: '{}',
  });
  assert.equal(invalid.status, 422);
});
