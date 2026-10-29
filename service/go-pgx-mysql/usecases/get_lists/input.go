package get_lists

import (
	"github.com/gofrs/uuid/v5"
)

type GetListsRequest struct {
	Page      int64
	AccountId uuid.UUID
}
