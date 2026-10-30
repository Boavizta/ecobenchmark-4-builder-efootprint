-- Version 1: identical starting state for every repetition, outside measurement.
INSERT INTO account (id, login, creation_date)
VALUES ('00000000-0000-4000-8000-000000000001', 'benchmark', '2024-01-01T00:00:00Z');
INSERT INTO list (id, account_id, name, creation_date)
SELECT md5('list-' || n)::uuid, '00000000-0000-4000-8000-000000000001',
       'list-' || n, '2024-01-01T00:00:00Z'
FROM generate_series(1, 30) AS n;
INSERT INTO task (id, list_id, name, description, creation_date)
SELECT md5('task-' || l || '-' || t)::uuid, md5('list-' || l)::uuid,
       'task-' || t, 'Hello World!', '2024-01-01T00:00:00Z'
FROM generate_series(1, 30) AS l CROSS JOIN generate_series(1, 20) AS t;
