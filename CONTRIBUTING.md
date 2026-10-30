# CONTRIBUTION GUIDE

The supported execution workflow is documented in [benchmark/README.md](benchmark/README.md).
`benchmark/` owns orchestration and measurement, `service/` contains implementations,
`migrations/` contains database schemas, and `test/` / `validator/` contain conformity tests.
`runner/` retains historical workloads; `benchmark/full_services.py` runs the mixed
journey across all implemented HTTP services with raw local resource observations.

## Service Contribution

Target folders :
- [/service](./service)

### Foreword

#### Definition

A service is a combination of a language, a web framework, dao/orm lib (optional) and a webserver (optional).

#### Name convention
`[ecosytem-]language-framework[-dao][-webserver]`

**Example** :
- go-pgx (go as the language, pgx as the dao lib)
- jvm-kotlin-spring (jvm as the ecosytem, kotlin as the language, spring as the framework)
- php-symfony-apache2 (php as the language, symfony as the framework, apache2 as the webserver).

#### Implementation Spirit

Remember that is not a  benchmark to make language competition. But an eco benchmark to identify which design choice got impact on web application footprint on our planet. Design should represent practices from the communities.

#### Degraded use case

In order to compare other design choice than framework and language, there is a list of predefined use case documented. [See use case documentation](./readme.md) Each use case got a design difference (and only one).

### Design rules

Each service must respect :
- an API contract, 
- a predefined set of SQL requests by API to respect.
- for some service, algorithm to respect.

Reference implementation is the [golang implementation](./service/go-pgx-pg).

### Acceptance criteria

Service should pass the [conformity tests](./test/check-service-conformity.feature) - For help to execute test go here : https://github.com/karatelabs/karate

Service's docker should have 2 environment variables :

- `DATABASE_URL` :  Example of value injected: postgres://postgres:mysecretpassword@database:5432/postgres - url signature can be change for each service
- `DATABASE_POOL_MAX` : setup to 20 by default

#### API Contract

API Contract must respect the following [API Definition documentation](./service/specs.md).

#### SQL requests

Each API endpoint must respect the following SQL request.

---
**NOTE**

Due to ORM behavior you may have small difference in the real generated SQL. Please just check if there is no major differences and document the minor differences.
___

##### POST /api/accounts

`INSERT INTO account(id, login, creation_date) values ($1, $2, $3);`

##### POST /api/accounts/:account/lists

`INSERT INTO list(id, account_id, name,  creation_date) values ($1, $2, $3, $4);`

##### POST /api/lists/:list/tasks

`INSERT INTO task(id, list_id, name, description, creation_date) values ($1, $2, $3, $4, $5);`

##### GET 	/api/accounts/:account/lists?page=n

`SELECT l.id, l.name, l.creation_date, l.account_id, t.id AS task_id, t.name AS task_name, t.description, t.creation_date AS task_creation_date
FROM list l LEFT JOIN task t ON l.id = t.list_id
WHERE l.account_id = $1 AND l.id IN (SELECT id FROM list WHERE account_id = $1 LIMIT $2 OFFSET $3)`

##### GET 	/api/stats

`select id,  login, count(list_id) as nb_list, round(avg(nb_tasks),2) as avg_tasks from (select account.id, account.login, list.id list_id, count(task.id) nb_tasks from account inner join list on (list.account_id=account.id) left join task on (task.list_id=list.id) group by account.id, account.login, list.id) t group by id, login`

#### Algorithm

##### GET 	/api/stats

Please follow the following example :

```go
for rowsList.Next() {
		var rawAccountId string
		var accountLogin sql.NullString
		var listCount int64
		var taskAvg float64
		err = rowsList.Scan(&rawAccountId, &accountLogin, &listCount, &taskAvg)
		if err != nil {
			return nil, errors.Wrap(err, "failed to scan the SQL result")
		}
		accountId, err := uuid.FromString(rawAccountId)
		if err != nil {
			return nil, errors.Wrapf(err, "the account has wrong id: %s", rawAccountId)
		}
		stat := get_stats.GetStatsByAccountsResponse{
			AccountId:    accountId,
			AccountLogin: accountLogin.String,
			ListCount:    listCount,
			TaskAvg:      taskAvg,
		}
		stats = append(stats, stat)
	}
	return stats, nil
```

## Benchmark and result contributions

Run `make test` before submitting orchestration changes. The shared lifecycle lives
in `benchmark/ecobench.py`; transport-specific command construction lives in
`benchmark/backends.py`. Add regression tests when changing either.

For local execution use `make benchmark-up`, `make benchmark-prepare`, and
`make benchmark-run`. For SSH deployment follow the dedicated-server setup guide.
Only the Go/PostgreSQL reference service is currently integrated into the two-host
Lima/SSH harness. For a one-run-per-service local Docker sweep, use
`python3 benchmark/full_services.py --output results/full-run`; see the limitations
and output formats in `benchmark/README.md`. Experimental branches changing the
protocol, indexes, pagination, aggregation design, or fixture size are separate
use cases, not silently interchangeable default-scope services.

Results are written under `results/` and are ignored by Git. Preserve raw observations,
units, hardware/image metadata, and failure status when proposing analysis or export
code. Never interpret CPU time as measured physical energy.
