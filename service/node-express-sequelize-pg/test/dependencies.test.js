const assert = require('node:assert/strict');
const { test } = require('node:test');
const express = require('express');
const bodyParser = require('body-parser');

process.env.DATABASE_URL = 'postgres://postgres:password@localhost/test';

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

test('list aggregation preserves empty lists and groups joined tasks', async () => {
  const models = require('../src/model');
  const sequelize = require('../src/service/database');
  const original = sequelize.query;
  sequelize.query = async () => [
    { id: 'first', account_id: 'account', name: 'first', creation_date: '2026-01-01', task_id: null },
    { id: 'second', account_id: 'account', name: 'second', creation_date: '2026-01-02', task_id: 'task1', task_name: 'one' },
    { id: 'second', account_id: 'account', name: 'second', creation_date: '2026-01-02', task_id: 'task2', task_name: 'two' },
  ];
  try {
    const lists = await models.list.findByAccount('account', 0);
    assert.equal(lists.length, 2);
    assert.deepEqual(lists[0].tasks, []);
    assert.equal(lists[0].creation_date, '2026-01-01');
    assert.equal(lists[0].account_id, 'account');
    assert.equal(lists[1].tasks.length, 2);
  } finally {
    sequelize.query = original;
  }
});
