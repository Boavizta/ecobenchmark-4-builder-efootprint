import http from 'k6/http';
import { check } from 'k6';

export const options = {
  scenarios: {
    workload: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.RATE || 10),
      timeUnit: '1s',
      duration: __ENV.DURATION || '30s',
      preAllocatedVUs: 20,
      maxVUs: 100,
      gracefulStop: '10s',
    },
  },
  thresholds: {
    checks: ['rate==1'],
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1000'],
    dropped_iterations: ['count==0'],
  },
};

export default function () {
  const path = __ENV.SCENARIO === 'DATA_SIMPLE_ANALYTIC'
    ? '/api/stats'
    : '/api/accounts/00000000-0000-4000-8000-000000000001/lists?page=0';
  const response = http.get(`${__ENV.SERVER_URL}${path}`);
  check(response, {
    'successful HTTP status': (r) => r.status >= 200 && r.status < 300,
    'nonempty JSON array': (r) => {
      try { const body = r.json(); return Array.isArray(body) && body.length > 0; }
      catch (_) { return false; }
    },
  });
}
