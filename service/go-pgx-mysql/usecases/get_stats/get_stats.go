package get_stats

import (
	"fmt"
)

type GetStatsByAccounts struct {
	Storage Storage
}

func (c *GetStatsByAccounts) Execute() ([]GetStatsByAccountsResponse, error) {
	stats, err := c.Storage.GetStatsByAccounts()
	if err != nil {
		return nil, fmt.Errorf("%s: %w", "failed to create the stats", err)
	}
	return stats, nil
}
