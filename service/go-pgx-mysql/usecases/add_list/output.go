package add_list

import (
	"github.com/gofrs/uuid/v5"
	"time"
)

type AddListResponse struct {
	Id           uuid.UUID
	Name         string
	CreationDate time.Time
	AccountId    uuid.UUID
}
