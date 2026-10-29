
class ListsController < ApplicationController
  before_action :load_account

  def index
    @list = ListResponse.generate(@account.id, params[:page])
    response.headers['Content-Type'] = 'application/json'
    render json: @list
  end

  def create
    @list = @account.lists.new(params.permit(:name))
    response.headers['Content-Type'] = 'application/json'
    if @list.save
      render json: @list, status: :created
    else
      render json: @list.errors, status: :bad_request
    end
  end

  private

  def load_account
    @account = Account.find(params[:account_id])
  end
end
