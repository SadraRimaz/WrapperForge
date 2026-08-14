package lib

// Task mirrors core/mock-api/contract.md's Task resource.
type Task struct {
	ID            string  `json:"id"`
	Title         string  `json:"title"`
	Done          bool    `json:"done"`
	DueDate       string  `json:"due_date"`
	PriorityScore float64 `json:"priority_score"`
	CreatedAt     string  `json:"created_at"`
}

// TaskUpdate is a partial update payload: only fields present on the
// wire should be applied. Pointer fields distinguish "omitted" from
// "explicitly set" for the client-building side.
type TaskUpdate struct {
	Title   *string `json:"title,omitempty"`
	Done    *bool   `json:"done,omitempty"`
	DueDate *string `json:"due_date,omitempty"`
}

// BulkUpdateItem is one entry in a bulk_update request.
type BulkUpdateItem struct {
	ID     string     `json:"id"`
	Fields TaskUpdate `json:"fields"`
}

// BulkUpdateFailure records one failed item from a bulk_update call.
// RawMessage is the backend's own error text for this item, carried
// through unchanged (see NotFoundError's RawBody doc for why); Err is
// the typed, errors.Is(ErrTaskNotFound)-checkable form for callers
// that want to branch on it programmatically.
type BulkUpdateFailure struct {
	ID         string
	Err        error
	RawMessage string
}

// BulkUpdateResult is the client-facing partial-failure representation
// for bulk_update: a per-item error slice, preserving input order.
type BulkUpdateResult struct {
	Succeeded []Task
	Failed    []BulkUpdateFailure
}

// wireBulkUpdateFailure is the wire shape of one failed item, as
// returned by both the direct backend and this wrapper's server:
// {id, error}. error text is intentionally not part of BulkUpdateFailure
// above (only id participates in QC comparison, per qc_interface.md).
type wireBulkUpdateFailure struct {
	ID    string `json:"id"`
	Error string `json:"error"`
}

// wireBulkUpdateResponse is the wire shape of a bulk_update response.
type wireBulkUpdateResponse struct {
	Succeeded []Task                  `json:"succeeded"`
	Failed    []wireBulkUpdateFailure `json:"failed"`
}
