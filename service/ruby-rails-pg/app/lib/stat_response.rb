class StatResponse
  attr_reader :account_id, :account_login, :list_count, :task_avg

  def self.generate
    stats = []
    sql_results.each do |sql_result|
      stats << new(sql_result)
    end
    stats
  end

  def initialize(sql_result)
    @account_id = sql_result["id"]
    @account_login = sql_result["login"]
    @list_count = sql_result["list_count"].to_i
    @task_avg = sql_result["task_avg"].to_f
  end

  def as_json(*)
    { account_id: account_id, account_login: account_login, list_count: list_count, task_avg: task_avg }
  end

  private

  def self.sql_results
    ActiveRecord::Base.connection.execute("
      SELECT id, login, COUNT(list_id) AS list_count, ROUND(AVG(nb_tasks), 2) AS task_avg
      FROM (
        SELECT account.id, account.login, list.id list_id, COUNT(task.id) nb_tasks
        FROM account
        INNER JOIN list ON (list.account_id = account.id)
        LEFT JOIN task ON (task.list_id = list.id)
        GROUP BY account.id, account.login, list.id
      ) t
      GROUP BY id, login
    ")
  end
end
