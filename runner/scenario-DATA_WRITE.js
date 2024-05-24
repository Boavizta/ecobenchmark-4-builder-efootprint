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
  for (let outerIndex = 0; outerIndex < 10; outerIndex++) {
    for (let innerIndex = 0; innerIndex < 3; innerIndex++) {
      // create a task list
      let listName = `user_${accountId}_list_${outerIndex}-${innerIndex}`;
      let list = json_post('list creation', `/api/accounts/${accountId}/lists`, { name: listName });
    
      for (let taskIndex = 0; taskIndex < 20; taskIndex++) {
        // create a task in the list
        let taskName = `${listName}_${taskIndex}`;
        json_post('task creation', `/api/lists/${list.id}/tasks`, {
          name: taskName,
          description: 'Hello World!',
        });
      }
    }
  }
}