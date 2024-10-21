import http from 'k6/http';
import { check, sleep } from 'k6';
import file from 'k6/x/file';

let loginIndex = 0;
let serverHost = __ENV.SERVER_HOST || 'localhost:8080';


const filepath = '/tmp/account_id';

function success_response(r) {
  return r.status >= 200 && r.status < 300;
}

let httpParams = {
  headers: {
    'Content-Type': 'application/json',
  },
};

function json_post(name, path, data) {
  let res = http.post(`http://${serverHost}${path}`, JSON.stringify(data), httpParams);
  check(res, { [name]: success_response });
  return res.json();
}

export default function() {
  const data = { login: `user_${loginIndex++}` };
  // login

  file.writeString(filepath, `PLOP`);
  let account = json_post('login', '/api/accounts', data);
  file.writeString(filepath, `PLOP2`);
  file.writeString(filepath, `${account}`);
}