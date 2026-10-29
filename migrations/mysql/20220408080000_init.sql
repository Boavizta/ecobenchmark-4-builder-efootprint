CREATE TABLE account
(
    id            BINARY(16) PRIMARY KEY,
    login         TEXT,
    creation_date TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6)
);

CREATE INDEX idx_account_creation_date ON account(creation_date);

CREATE TABLE list
(
    id            BINARY(16) PRIMARY KEY,
    account_id    BINARY(16),
    name          TEXT,
    creation_date TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
    FOREIGN KEY (account_id) REFERENCES account(id)
);

CREATE INDEX idx_list_account_id ON list(account_id);
CREATE INDEX idx_list_creation_date ON list(creation_date);

CREATE TABLE task
(
    id            BINARY(16) PRIMARY KEY,
    list_id       BINARY(16),
    name          TEXT,
    description   TEXT,
    creation_date TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
    FOREIGN KEY (list_id) REFERENCES list(id)
);

CREATE INDEX idx_task_list_id ON task(list_id);
CREATE INDEX idx_task_creation_date ON task(creation_date);
