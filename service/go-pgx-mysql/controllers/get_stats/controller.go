package get_stats

import (
	"fmt"
	echo "github.com/labstack/echo/v5"
	"go_pgx/usecases/get_stats"
	"log"
	"net/http"
)

func Controller(storage get_stats.Storage) func(c *echo.Context) error {
	useCase := get_stats.GetStatsByAccounts{Storage: storage}

	return func(c *echo.Context) error {

		stats, err := useCase.Execute()

		if err != nil {
			log.Printf("%+v", fmt.Errorf("%s: %w", "failed to handle the request to get the stats", err))
			return c.String(http.StatusInternalServerError, "failed to add the stats")
		}

		return c.JSON(
			http.StatusCreated,
			statsToResponse(stats),
		)
	}

}

func statsToResponse(stats []get_stats.GetStatsByAccountsResponse) []responseBody {
	response := make([]responseBody, len(stats))
	for i, s := range stats {
		response[i] = responseBody{
			AccountId:    s.AccountId.String(),
			AccountLogin: s.AccountLogin,
			ListCount:    s.ListCount,
			TaskAvg:      s.TaskAvg,
		}
	}
	return response
}
