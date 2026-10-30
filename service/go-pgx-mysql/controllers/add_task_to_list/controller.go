package add_task_to_list

import (
	"fmt"
	"github.com/gofrs/uuid/v5"
	echo "github.com/labstack/echo/v5"
	"go_pgx/common"
	"go_pgx/usecases/add_task_to_list"
	"log"
	"net/http"
)

func Controller(storage add_task_to_list.Storage) func(c *echo.Context) error {
	useCase := add_task_to_list.AddTask{Storage: storage}

	return func(c *echo.Context) error {
		request := requestBody{}
		if err := c.Bind(&request); err != nil {
			return c.NoContent(http.StatusBadRequest)
		}

		listId, err := uuid.FromString(c.Param("list_id"))
		if err != nil {
			return c.NoContent(http.StatusBadRequest)
		}

		requestTask := add_task_to_list.AddTaskRequest{
			Name:        request.Name,
			Description: request.Description,
			ListId:      listId,
		}

		createdTask, err := useCase.Execute(requestTask)

		if err != nil {
			log.Printf("%+v", fmt.Errorf("%s: %w", "failed to handle the request to add the task", err))
			return c.String(http.StatusInternalServerError, "failed to add the task")
		}

		return c.JSON(
			http.StatusCreated,
			responseBody{
				Id:           createdTask.Id.String(),
				ListId:       createdTask.ListId.String(),
				Name:         createdTask.Name,
				Description:  createdTask.Description,
				CreationDate: common.JSONDATE{Time: createdTask.CreationDate},
			},
		)
	}

}
