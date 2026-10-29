
class ListsController < ApplicationController
  def index
    @list = ListResponse.generate(params[:account_id], params[:page])
    response.headers['Content-Type'] = 'application/json'
    render json: @list
  end

  def create
    @list = List.new(params.permit(:name).merge(account_id: params[:account_id]))
    response.headers['Content-Type'] = 'application/json'
    if @list.save
      render json: @list, status: :created
    else
      render json: @list.errors, status: :bad_request
    end
  end

end
