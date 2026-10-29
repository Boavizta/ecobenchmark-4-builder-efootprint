class Task < ApplicationRecord
  self.table_name = "task"

  # Parent integrity is checked by the shared database FK, not an extra SELECT.
  belongs_to :list, optional: true
end
