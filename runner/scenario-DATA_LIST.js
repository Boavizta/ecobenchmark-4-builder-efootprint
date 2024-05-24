import http from 'k6/http';
import { check, sleep } from 'k6';

let loginIndex = 0;
let serverHost = __ENV.SERVER_HOST || 'localhost:8080';
let accountId= __ENV.ACCOUNT_ID;

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

    // list tasks
    for (let page = 0;; page++) {
      let listRes = http.get(`http://${serverHost}/api/accounts/${accountId}/lists?page=${page}`);
      check(listRes, { 'success listing': success_response });
      if (listRes.json().length === 0) {
        break;
      }
    }
  }