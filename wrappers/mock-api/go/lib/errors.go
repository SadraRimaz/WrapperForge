package lib

import (
	"encoding/json"
	"errors"
	"fmt"
)

// ErrTaskNotFound is the sentinel error for a not-found id, per
// contract.md's "Not found" case (get/update/delete/bulk_update items).
// Callers should check with errors.Is; *NotFoundError satisfies it via
// its Is method.
var ErrTaskNotFound = errors.New("task not found")

// NotFoundError is the concrete not-found error returned by client
// methods. It carries the backend's raw response body so a caller
// (e.g. the QC server) can proxy the exact error content through
// rather than re-deriving its own wording.
type NotFoundError struct {
	TaskID  string
	RawBody json.RawMessage
}

func (e *NotFoundError) Error() string {
	return fmt.Sprintf("task not found: %s", e.TaskID)
}

// Is lets errors.Is(err, ErrTaskNotFound) match a *NotFoundError.
func (e *NotFoundError) Is(target error) bool {
	return target == ErrTaskNotFound
}

// ValidationError represents contract.md's "Invalid input" case:
// a client-supplied field failed its type/format requirement.
// Callers should check with errors.As. RawBody carries the backend's
// raw response body for the same proxying reason as NotFoundError.
type ValidationError struct {
	RawBody json.RawMessage
}

func (e *ValidationError) Error() string {
	return "invalid input: " + string(e.RawBody)
}

// unexpectedStatusError wraps an HTTP status this client didn't expect
// for the operation it was performing (neither the documented success
// code nor a recognized error code).
type unexpectedStatusError struct {
	Op     string
	Status int
	Body   string
}

func (e *unexpectedStatusError) Error() string {
	return fmt.Sprintf("%s: unexpected status %d: %s", e.Op, e.Status, e.Body)
}
