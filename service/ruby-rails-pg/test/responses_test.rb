require "minitest/autorun"
require "minitest/mock"
require_relative "../app/lib/task_response"
require_relative "../app/lib/list_response"
require_relative "../app/lib/stat_response"

class ResponsesTest < Minitest::Test
  def row(task_id: nil)
    {
      "id" => "list-id", "account_id" => "account-id", "name" => "list",
      "creation_date" => "2026-10-29T00:00:00Z", "task_id" => task_id,
      "task_name" => "task", "description" => "description",
      "task_creation_date" => "2026-10-29T00:00:00Z"
    }
  end

  def test_empty_join_does_not_create_a_phantom_task
    ListResponse.stub(:sql_results, [row]) do
      lists = ListResponse.generate("account-id", 0)
      assert_equal 1, lists.length
      assert_empty lists.first.tasks
    end
  end

  def test_page_one_is_forwarded_without_subtracting_one
    received_page = nil
    query = ->(_account_id, page) { received_page = page; [] }
    ListResponse.stub(:sql_results, query) { ListResponse.generate("account-id", 1) }
    assert_equal 1, received_page
  end

  def test_joined_tasks_remain_grouped_without_losing_the_first_task
    ListResponse.stub(:sql_results, [row(task_id: "first"), row(task_id: "second")]) do
      lists = ListResponse.generate("account-id", 0)
      assert_equal 1, lists.length
      assert_equal %w[first second], lists.first.tasks.map(&:id)
    end
  end

  def test_fractional_statistics_are_preserved
    stat = StatResponse.new("id" => "account-id", "login" => "login",
                            "list_count" => 2, "task_avg" => "1.5")
    assert_equal 1.5, stat.task_avg
  end
end
