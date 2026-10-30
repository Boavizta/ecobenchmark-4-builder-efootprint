import http from 'k6/http';
import { check, fail, sleep } from 'k6';
import { Counter } from 'k6/metrics';

const base = `http://${__ENV.SERVER_HOST || 'service:8080'}`;
const params = { headers: { 'Content-Type': 'application/json' }, timeout: '5s' };
const scenarioErrors = new Counter('scenario_errors');

export const options = {
  scenarios: {
    smoke: { executor: 'constant-vus', vus: 1, duration: __ENV.DURATION || '10s', gracefulStop: '10s' },
  },
  thresholds: {
    checks: ['rate==1'],
    http_req_failed: ['rate==0'],
    iterations: ['count>0'],
    scenario_errors: ['count==0'],
  },
};

function request(name, path, payload) {
  const response = payload === undefined
    ? http.get(base + path, params)
    : http.post(base + path, JSON.stringify(payload), params);
  if (!check(response, { [`${name}: HTTP success`]: r => r.status >= 200 && r.status < 300 })) {
    sleep(0.1);
    fail(`${name}: HTTP ${response.status}: ${response.body}`);
  }
  try {
    return response.json();
  } catch (_) {
    fail(`${name}: response is not JSON: ${response.body}`);
  }
}

function expect(value, name, predicate) {
  if (!check(value, { [name]: predicate })) {
    sleep(0.1);
    fail(`${name}: ${JSON.stringify(value)}`);
  }
}

export default function () {
  scenarioErrors.add(0);
  try {
    journey();
  } catch (error) {
    scenarioErrors.add(1);
    sleep(0.1);
    throw error;
  }
}

function journey() {
  const login = `smoke-${__VU}-${__ITER}-${Date.now()}`;
  const account = request('create account', '/api/accounts', { login });
  expect(account, 'account has ID and requested login', a => typeof a.id === 'string' && a.login === login);
  const path = `/api/accounts/${account.id}/lists`;
  const first = request('create first list', path, { name: 'first' });
  const second = request('create second list', path, { name: 'second' });
  expect(first, 'first list has ID', l => typeof l.id === 'string');
  expect(second, 'second list has ID', l => typeof l.id === 'string');
  const empty = request('read lists without tasks', path);
  expect(empty, 'empty lists are returned without phantom tasks', lists =>
    Array.isArray(lists) && lists.length === 2 && lists.every(l => Array.isArray(l.tasks) && l.tasks.length === 0));
  expect(empty, 'list creation dates are present and valid', lists =>
    lists.every(l => typeof l.creation_date === 'string' && Date.parse(l.creation_date) > Date.UTC(2000, 0, 1)));

  const expectedTasks = new Map();
  for (const [list, count] of [[first, 1], [second, 2]]) {
    for (let i = 0; i < count; i++) {
      const task = request('create task', `/api/lists/${list.id}/tasks`, {
        name: `task-${i}`, description: 'smoke benchmark',
      });
      expect(task, 'task has ID and description', t => typeof t.id === 'string' && t.description === 'smoke benchmark');
      expectedTasks.set(task.id, `task-${i}`);
    }
  }
  const lists = request('read populated lists', path);
  expect(lists, 'lists contain exactly three persisted tasks', rows => Array.isArray(rows) && rows.length === 2 &&
    rows.every(l => l.id === first.id || l.id === second.id) &&
    rows.find(l => l.id === first.id).tasks.length === 1 && rows.find(l => l.id === second.id).tasks.length === 2);
  expect(lists, 'persisted task IDs names and descriptions match writes', rows =>
    rows.every(l => l.tasks.every(t => expectedTasks.has(t.id) &&
      t.name === expectedTasks.get(t.id) && t.description === 'smoke benchmark')));
  const next = request('read next page', `${path}?page=1`);
  expect(next, 'next page is empty', rows => Array.isArray(rows) && rows.length === 0);
  const stats = request('read statistics', '/api/stats');
  expect(stats, 'statistics preserve list count and fractional average', rows => {
    if (!Array.isArray(rows)) return false;
    const row = rows.find(r => r.account_id === account.id);
    return row && Number(row.list_count) === 2 && Number(row.task_avg) === 1.5;
  });
  sleep(0.1);
}

export function handleSummary(data) {
  return {
    '/results/summary.json': JSON.stringify(data, null, 2),
    stdout: `Iterations: ${data.metrics.iterations ? data.metrics.iterations.values.count : 0}\n`,
  };
}
