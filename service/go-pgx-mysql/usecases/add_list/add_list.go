package add_list

import (
	"fmt"
	"github.com/gofrs/uuid/v5"
	"time"
)

type AddList struct {
	Storage Storage
}

func (c *AddList) Execute(request AddListRequest) (*AddListResponse, error) {
	id, err := uuid.NewV4()
	if err != nil {
		return nil, fmt.Errorf("%s: %w", "failed to generate uuid", err)
	}

	listResponse := &AddListResponse{
		Id:           id,
		Name:         request.Name,
		AccountId:    request.AccountId,
		CreationDate: time.Now().UTC(),
	}

	err = c.Storage.AddList(listResponse)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", fmt.Sprintf("failed to create the list %s", request.Name), err)
	}

	return listResponse, nil
}
