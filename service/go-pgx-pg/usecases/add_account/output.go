package add_account

import (
	"github.com/gofrs/uuid/v5"
	"time"
)

type AddAccountResponse struct {
	Id           uuid.UUID
	Login        string
	CreationDate time.Time
}
