
class TasksController < ApplicationController
  def create
    @task = Task.new(params.permit(:name, :description).merge(list_id: params[:list_id]))
    response.headers['Content-Type'] = 'application/json'
    if @task.save
      render json: @task, status: :created
    else
      render json: @task.errors, status: :bad_request
    end
  end

end
