class List < ApplicationRecord
  self.table_name = "list"

  # Parent integrity is checked by the shared database FK, not an extra SELECT.
  belongs_to :account, optional: true
  has_many :tasks

  validates :name, presence: true
end
