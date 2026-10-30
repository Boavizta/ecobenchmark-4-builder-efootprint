package add_account

import (
	"fmt"
	"github.com/gofrs/uuid/v5"
	"time"
)

type AddAccount struct {
	Storage Storage
}

func (c *AddAccount) Execute(requestLogin string) (*AddAccountResponse, error) {
	id, err := uuid.NewV4()
	if err != nil {
		return nil, fmt.Errorf("%s: %w", "failed to generate uuid", err)
	}

	accountResponse := &AddAccountResponse{
		Id:           id,
		Login:        requestLogin,
		CreationDate: time.Now().UTC(),
	}

	err = c.Storage.AddAccount(accountResponse)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", fmt.Sprintf("failed to create the account %s", requestLogin), err)
	}

	return accountResponse, nil
}
