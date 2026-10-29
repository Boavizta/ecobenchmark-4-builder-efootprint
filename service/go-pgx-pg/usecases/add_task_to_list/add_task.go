package add_task_to_list

import (
	"fmt"
	"github.com/gofrs/uuid/v5"
	"time"
)

type AddTask struct {
	Storage Storage
}

func (c *AddTask) Execute(request AddTaskRequest) (*AddTaskResponse, error) {
	id, err := uuid.NewV4()
	if err != nil {
		return nil, fmt.Errorf("%s: %w", "failed to generate uuid", err)
	}

	taskResponse := &AddTaskResponse{
		Id:           id,
		Name:         request.Name,
		Description:  request.Description,
		ListId:       request.ListId,
		CreationDate: time.Now().UTC(),
	}

	err = c.Storage.AddTask(taskResponse)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", fmt.Sprintf("failed to create the task %s", request.Name), err)
	}

	return taskResponse, nil
}
