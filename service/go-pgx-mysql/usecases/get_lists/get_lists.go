package get_lists

import (
	"fmt"
)

type GetListsByAccountId struct {
	Storage Storage
}

func (c *GetListsByAccountId) Execute(request GetListsRequest) ([]GetListsResponse, error) {

	response, err := c.Storage.GetListsByAccountId(request)

	if err != nil {
		return nil, fmt.Errorf("%s: %w", fmt.Sprintf("failed to get the lists of account id %s", request.AccountId.String()), err)
	}

	return response, nil
}
