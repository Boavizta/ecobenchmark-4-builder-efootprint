class AccountsController < ApplicationController
  def create
    @account = Account.new(login: params[:login])
    response.headers['Content-Type'] = 'application/json'
    if @account.save
      render json: @account, status: :created
    else
      render json: @account.errors, status: :bad_request
    end
  end
end
