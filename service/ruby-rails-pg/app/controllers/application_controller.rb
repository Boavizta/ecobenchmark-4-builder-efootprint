class ApplicationController < ActionController::API
  rescue_from ActiveRecord::InvalidForeignKey do
    head :bad_request
  end
end
