package get_lists

import (
	"encoding/json"
	"go_pgx/usecases/get_lists"
	"testing"
)

func TestEmptyListSerializesTasksAsArray(t *testing.T) {
	body, err := json.Marshal(listToResponse([]get_lists.GetListsResponse{{}}))
	if err != nil {
		t.Fatal(err)
	}
	var lists []map[string]json.RawMessage
	if err := json.Unmarshal(body, &lists); err != nil {
		t.Fatal(err)
	}
	if string(lists[0]["tasks"]) != "[]" {
		t.Fatalf("expected tasks: [], got %s", body)
	}
}
