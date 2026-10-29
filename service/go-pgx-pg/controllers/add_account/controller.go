package add_account

import (
	"fmt"
	echo "github.com/labstack/echo/v5"
	"go_pgx/common"
	"go_pgx/usecases/add_account"
	"log"
	"net/http"
)

func Controller(storage add_account.Storage) func(c *echo.Context) error {
	useCase := add_account.AddAccount{Storage: storage}

	return func(c *echo.Context) error {
		request := requestBody{}
		if err := c.Bind(&request); err != nil {
			return c.NoContent(http.StatusBadRequest)
		}

		createdAccount, err := useCase.Execute(request.Login)

		if err != nil {
			log.Printf("%+v", fmt.Errorf("%s: %w", "failed to handle the request to add the account", err))
			return c.String(http.StatusInternalServerError, "failed to add the account")
		}

		return c.JSON(
			http.StatusCreated,
			responseBody{
				Id:           createdAccount.Id.String(),
				Login:        createdAccount.Login,
				CreationDate: common.JSONDATE{Time: createdAccount.CreationDate},
			},
		)
	}

}
