// Package lib is the Tasks API client library: one typed method per
// core/mock-api/contract.md operation, calling the real backend's HTTP
// API directly (POST /tasks, GET /tasks/{id}, ...).
package lib

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
)

// Client is a Tasks API client bound to a single backend base URL.
type Client struct {
	baseURL    string
	httpClient *http.Client
}

// NewClient builds a Client against baseURL (e.g. "http://127.0.0.1:8000").
func NewClient(baseURL string) *Client {
	return &Client{baseURL: baseURL, httpClient: http.DefaultClient}
}

// doRequest sends method/path with an optional JSON body and returns
// the HTTP status code plus the raw response body. Only transport-level
// failures (connection errors) are returned as an error here — non-2xx
// statuses are returned normally, raw body included, for the caller to
// interpret (and, for error statuses, to proxy through unchanged).
func (c *Client) doRequest(ctx context.Context, method, path string, body any) (int, []byte, error) {
	var reqBody io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return 0, nil, fmt.Errorf("marshal request body: %w", err)
		}
		reqBody = bytes.NewReader(b)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, reqBody)
	if err != nil {
		return 0, nil, fmt.Errorf("build request: %w", err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return 0, nil, fmt.Errorf("%s %s: %w", method, path, err)
	}
	defer resp.Body.Close()

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return resp.StatusCode, nil, fmt.Errorf("read response body: %w", err)
	}

	return resp.StatusCode, raw, nil
}

// notFoundOrValidationError builds the appropriate typed error for a
// 404 or 422 status, carrying the backend's raw body through for
// proxying, or an unexpectedStatusError for anything else undocumented
// for the given operation.
func notFoundOrValidationError(op, id string, status int, raw []byte) error {
	switch status {
	case http.StatusNotFound:
		return &NotFoundError{TaskID: id, RawBody: json.RawMessage(raw)}
	case http.StatusUnprocessableEntity:
		return &ValidationError{RawBody: json.RawMessage(raw)}
	default:
		return &unexpectedStatusError{Op: op, Status: status, Body: string(raw)}
	}
}

// Create creates a task. title and dueDate (YYYY-MM-DD) are required
// per contract.md; id/priority_score/created_at are server-generated,
// done starts false.
func (c *Client) Create(ctx context.Context, title string, dueDate string) (*Task, error) {
	reqBody := map[string]string{"title": title, "due_date": dueDate}
	status, raw, err := c.doRequest(ctx, http.MethodPost, "/tasks", reqBody)
	if err != nil {
		return nil, err
	}
	if status != http.StatusCreated {
		return nil, notFoundOrValidationError("Create", "", status, raw)
	}
	var task Task
	if err := json.Unmarshal(raw, &task); err != nil {
		return nil, fmt.Errorf("decode response body: %w", err)
	}
	return &task, nil
}

// CreateRaw forwards body verbatim to POST /tasks, preserving exactly
// which fields the caller did or didn't include on the wire. Create's
// (title, dueDate string) signature can't represent "field omitted"
// (Go strings have no unset state), but contract.md's invalid-input
// case explicitly includes a genuinely-missing required field — so the
// QC server uses this instead of Create when replaying an incoming
// request that may be missing title/due_date, to stay faithful to what
// the caller actually sent.
func (c *Client) CreateRaw(ctx context.Context, body json.RawMessage) (*Task, error) {
	status, raw, err := c.doRequest(ctx, http.MethodPost, "/tasks", body)
	if err != nil {
		return nil, err
	}
	if status != http.StatusCreated {
		return nil, notFoundOrValidationError("Create", "", status, raw)
	}
	var task Task
	if err := json.Unmarshal(raw, &task); err != nil {
		return nil, fmt.Errorf("decode response body: %w", err)
	}
	return &task, nil
}

// Get returns the task matching id, or a *NotFoundError if it doesn't exist.
func (c *Client) Get(ctx context.Context, id string) (*Task, error) {
	status, raw, err := c.doRequest(ctx, http.MethodGet, "/tasks/"+url.PathEscape(id), nil)
	if err != nil {
		return nil, err
	}
	if status != http.StatusOK {
		return nil, notFoundOrValidationError("Get", id, status, raw)
	}
	var task Task
	if err := json.Unmarshal(raw, &task); err != nil {
		return nil, fmt.Errorf("decode response body: %w", err)
	}
	return &task, nil
}

// List returns all tasks, optionally filtered by done. Pass nil for
// done to omit the filter and return every task.
func (c *Client) List(ctx context.Context, done *bool) ([]Task, error) {
	path := "/tasks"
	if done != nil {
		path += "?done=" + strconv.FormatBool(*done)
	}
	status, raw, err := c.doRequest(ctx, http.MethodGet, path, nil)
	if err != nil {
		return nil, err
	}
	if status != http.StatusOK {
		return nil, notFoundOrValidationError("List", "", status, raw)
	}
	var tasks []Task
	if err := json.Unmarshal(raw, &tasks); err != nil {
		return nil, fmt.Errorf("decode response body: %w", err)
	}
	if tasks == nil {
		tasks = []Task{}
	}
	return tasks, nil
}

// Update applies a partial update to the task matching id. Only fields
// set (non-nil) in fields are changed. Returns a *NotFoundError if id
// doesn't exist, or a *ValidationError if a present field is malformed.
func (c *Client) Update(ctx context.Context, id string, fields TaskUpdate) (*Task, error) {
	status, raw, err := c.doRequest(ctx, http.MethodPatch, "/tasks/"+url.PathEscape(id), fields)
	if err != nil {
		return nil, err
	}
	if status != http.StatusOK {
		return nil, notFoundOrValidationError("Update", id, status, raw)
	}
	var task Task
	if err := json.Unmarshal(raw, &task); err != nil {
		return nil, fmt.Errorf("decode response body: %w", err)
	}
	return &task, nil
}

// Delete permanently removes the task matching id. Returns a
// *NotFoundError if id doesn't exist.
func (c *Client) Delete(ctx context.Context, id string) error {
	status, raw, err := c.doRequest(ctx, http.MethodDelete, "/tasks/"+url.PathEscape(id), nil)
	if err != nil {
		return err
	}
	if status != http.StatusNoContent {
		return notFoundOrValidationError("Delete", id, status, raw)
	}
	return nil
}

// BulkUpdate applies each item's update independently. An item with an
// unknown id fails on its own (recorded in the result's Failed slice,
// with the backend's own error text carried through unchanged) without
// aborting the batch; every other item is still attempted. The
// returned error is non-nil only for whole-call failures (network
// error, malformed request) — never for a per-item not-found.
func (c *Client) BulkUpdate(ctx context.Context, items []BulkUpdateItem) (*BulkUpdateResult, error) {
	reqBody := map[string][]BulkUpdateItem{"items": items}
	status, raw, err := c.doRequest(ctx, http.MethodPost, "/tasks/bulk_update", reqBody)
	if err != nil {
		return nil, err
	}
	if status != http.StatusOK {
		return nil, notFoundOrValidationError("BulkUpdate", "", status, raw)
	}

	var wire wireBulkUpdateResponse
	if err := json.Unmarshal(raw, &wire); err != nil {
		return nil, fmt.Errorf("decode response body: %w", err)
	}

	result := &BulkUpdateResult{
		Succeeded: wire.Succeeded,
		Failed:    make([]BulkUpdateFailure, 0, len(wire.Failed)),
	}
	for _, f := range wire.Failed {
		result.Failed = append(result.Failed, BulkUpdateFailure{
			ID:         f.ID,
			Err:        &NotFoundError{TaskID: f.ID},
			RawMessage: f.Error,
		})
	}
	return result, nil
}
