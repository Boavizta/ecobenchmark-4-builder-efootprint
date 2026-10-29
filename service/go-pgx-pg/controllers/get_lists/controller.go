package get_lists

import (
	"fmt"
	"github.com/gofrs/uuid/v5"
	echo "github.com/labstack/echo/v5"
	"go_pgx/common"
	"go_pgx/usecases/get_lists"
	"log"
	"net/http"
	"strconv"
)

func Controller(storage get_lists.Storage) func(c *echo.Context) error {
	useCase := get_lists.GetListsByAccountId{Storage: storage}

	return func(c *echo.Context) error {

		accountId, err := uuid.FromString(c.Param("account_id"))
		if err != nil {
			return c.NoContent(http.StatusBadRequest)
		}

		page, err := strconv.ParseInt(c.QueryParam("page"), 6, 12)
		if err != nil {
			page = 0
		}

		requestLists := get_lists.GetListsRequest{
			AccountId: accountId,
			Page:      page,
		}

		lists, err := useCase.Execute(requestLists)

		if err != nil {
			log.Printf("%+v", fmt.Errorf("%s: %w", "failed to handle the request to get the lists", err))
			return c.String(http.StatusInternalServerError, "failed to add the lists")
		}

		return c.JSON(
			http.StatusCreated,
			listToResponse(lists),
		)
	}

}

func listToResponse(tasks []get_lists.GetListsResponse) []responseBody {
	response := make([]responseBody, len(tasks))
	for i, l := range tasks {
		response[i] = responseBody{
			Id:           l.Id.String(),
			CreationDate: common.JSONDATE{Time: l.CreationDate},
			Name:         l.Name,
			AccountId:    l.AccountId.String(),
			Tasks:        taskToResponse(l.Tasks),
		}
	}
	return response
}

func taskToResponse(tasks []get_lists.TasksResponse) []TaskBody {
	response := make([]TaskBody, len(tasks))
	for i, t := range tasks {
		response[i] = TaskBody{
			Id:           t.Id.String(),
			CreationDate: common.JSONDATE{Time: t.CreationDate},
			Name:         t.Name,
			Description:  t.Description,
		}
	}
	return response
}
