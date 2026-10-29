ENV["RAILS_ENV"] ||= "test"
require_relative "../config/environment"
require "minitest/autorun"
require "rack/test"
require "securerandom"

# Run only against a fresh disposable benchmark database (DATABASE_URL).
# Do not use rails/test_help: the shared SQL migrations, not Rails, own this schema.
class ApiTest < Minitest::Test
  include Rack::Test::Methods

  def app
    Rails.application
  end

  def create(path, payload)
    post path, JSON.generate(payload), "CONTENT_TYPE" => "application/json"
    assert_equal 201, last_response.status, last_response.body
    JSON.parse(last_response.body)
  end

  def read(path, params = {})
    get path, params
    assert_equal 200, last_response.status, last_response.body
    JSON.parse(last_response.body)
  end

  def account
    create("/api/accounts", login: "rails-test-#{SecureRandom.uuid}")
  end

  def test_healthcheck
    head "/healthcheck"
    assert_equal 204, last_response.status
  end

  def test_empty_and_populated_lists_preserve_content_and_fractional_statistics
    owner = account
    path = "/api/accounts/#{owner.fetch('id')}/lists"
    # These strings were corrupted by the upstream JSON-wide gsub calls.
    name = "creationDate accountId listId accountLogin listCount taskAvg"
    first = create(path, name: name)
    second = create(path, name: "second")
    assert_equal name, first.fetch("name")
    lists = read(path)
    assert_equal 2, lists.size
    assert lists.all? { |list| list.fetch("tasks") == [] }

    expected = []
    [[first, 1], [second, 2]].each do |list, count|
      count.times do
        task = create("/api/lists/#{list.fetch('id')}/tasks", name: name, description: name)
        assert_equal name, task.fetch("name")
        assert_equal name, task.fetch("description")
        expected << task.fetch("id")
      end
    end
    lists = read(path)
    tasks = lists.flat_map { |list| list.fetch("tasks") }
    assert_equal expected.sort, tasks.map { |task| task.fetch("id") }.sort
    tasks.each do |task|
      assert_equal name, task.fetch("name")
      assert_equal name, task.fetch("description")
      assert task.fetch("creation_date")
    end
    stats = read("/api/stats").find { |stat| stat.fetch("account_id") == owner.fetch("id") }
    assert_equal 2, stats.fetch("list_count")
    assert_equal 1.5, stats.fetch("task_avg")
  end

  def test_zero_based_pagination_returns_each_list_once_and_then_stops
    owner = account
    path = "/api/accounts/#{owner.fetch('id')}/lists"
    expected = 23.times.map { |i| create(path, name: "page-list-#{i}").fetch("id") }
    pages = (0..3).map { |page| read(path, page: page) }
    assert_equal [10, 10, 3, 0], pages.map(&:size)
    actual = pages.flatten.map { |list| list.fetch("id") }
    assert_equal expected.sort, actual.sort
    assert_equal 23, actual.uniq.size
  end
end
