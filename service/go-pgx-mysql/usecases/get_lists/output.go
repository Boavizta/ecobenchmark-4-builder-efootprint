package get_lists

import (
	"github.com/gofrs/uuid/v5"
	"time"
)

type GetListsResponse struct {
	Id           uuid.UUID
	Name         string
	CreationDate time.Time
	AccountId    uuid.UUID
	Tasks        []TasksResponse
}

type TasksResponse struct {
	Id           uuid.UUID
	Name         string
	Description  string
	CreationDate time.Time
}
