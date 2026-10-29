package add_list

import (
	"github.com/gofrs/uuid/v5"
)

type AddListRequest struct {
	Name      string
	AccountId uuid.UUID
}
