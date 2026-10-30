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

test('list aggregation groups binary IDs by value and omits null tasks', async () => {
  const models = require('../src/model');
  const sequelize = require('../src/service/database');
  const { toBinaryUUID } = require('@hypercharlie/sequelize-binary-uuid');
  const id = '00000000-0000-4000-8000-000000000001';
  const second = '00000000-0000-4000-8000-000000000002';
  const original = sequelize.query;
  sequelize.query = async () => [
    { id: toBinaryUUID(id), account_id: toBinaryUUID(id), name: 'first', creation_date: '2026-01-01', task_id: null },
    { id: toBinaryUUID(second), account_id: toBinaryUUID(id), name: 'second', task_id: toBinaryUUID(id), task_name: 'one' },
    { id: toBinaryUUID(second), account_id: toBinaryUUID(id), name: 'second', task_id: toBinaryUUID(second), task_name: 'two' },
  ];
  try {
    const lists = await models.list.findByAccount(id, 0);
    assert.equal(lists.length, 2);
    assert.deepEqual(lists[0].tasks, []);
    assert.equal(lists[0].creation_date, '2026-01-01');
    assert.equal(lists[0].account_id, id);
    assert.equal(lists[1].tasks.length, 2);
  } finally {
    sequelize.query = original;
  }
});

test('statistics decode account IDs with the same binary UUID layout as writes', async () => {
  const models = require('../src/model');
  const sequelize = require('../src/service/database');
  const { toBinaryUUID } = require('@hypercharlie/sequelize-binary-uuid');
  const id = '12345678-abcd-4000-8000-123456789abc';
  const original = sequelize.query;
  sequelize.query = async () => [{ account_id: toBinaryUUID(id), list_count: 2, task_avg: '1.50' }];
  try {
    const rows = await models.account.statistics();
    assert.equal(rows[0].account_id, id);
    assert.equal(Number(rows[0].task_avg), 1.5);
  } finally {
    sequelize.query = original;
  }
});
