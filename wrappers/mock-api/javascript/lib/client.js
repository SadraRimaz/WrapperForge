/**
 * Tasks API client library: one typed async method per
 * core/mock-api/contract.md operation, calling the real backend's HTTP
 * API directly (POST /tasks, GET /tasks/{id}, ...) via global fetch.
 */

import { TaskNotFoundError, TaskValidationError } from "./errors.js";

/** @typedef {import("./models.js").Task} Task */
/** @typedef {import("./models.js").TaskUpdateFields} TaskUpdateFields */
/** @typedef {import("./models.js").BulkUpdateItem} BulkUpdateItem */
/** @typedef {import("./models.js").BulkUpdateResult} BulkUpdateResult */

/**
 * Builds the typed error for a non-success status, carrying the
 * backend's raw parsed body through unchanged (see errors.js).
 * @param {number} status
 * @param {string|undefined} id
 * @param {*} body
 * @returns {Error}
 */
function taskError(status, id, body) {
  if (status === 404) return new TaskNotFoundError(id, body);
  if (status === 422) return new TaskValidationError(body);
  return new Error(`unexpected status ${status}: ${JSON.stringify(body)}`);
}

export class TaskClient {
  /**
   * @param {string} [baseUrl] - e.g. "http://127.0.0.1:8000".
   */
  constructor(baseUrl = "http://127.0.0.1:8000") {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  /**
   * @param {string} method
   * @param {string} path
   * @param {*} [body] - Omit entirely (not `null`) to send no request body.
   * @returns {Promise<{status: number, body: *}>}
   */
  async #request(method, path, body) {
    /** @type {RequestInit} */
    const init = { method };
    if (body !== undefined) {
      init.headers = { "Content-Type": "application/json" };
      init.body = JSON.stringify(body);
    }
    const res = await fetch(`${this.baseUrl}${path}`, init);
    const text = await res.text();
    const parsed = text ? JSON.parse(text) : null;
    return { status: res.status, body: parsed };
  }

  /**
   * Creates a task. `title`/`dueDate` map to contract.md's required
   * `title`/`due_date`. A `dueDate` of `undefined` is omitted from the
   * request body entirely (rather than sent as `null`), so a caller
   * replaying a request that never included it stays faithful to what
   * was actually sent.
   * @param {string} title
   * @param {string} dueDate - ISO 8601 date (YYYY-MM-DD).
   * @returns {Promise<Task>}
   */
  async create(title, dueDate) {
    const { status, body } = await this.#request("POST", "/tasks", {
      title,
      due_date: dueDate,
    });
    if (status !== 201) throw taskError(status, undefined, body);
    return /** @type {Task} */ (body);
  }

  /**
   * @param {string} id
   * @returns {Promise<Task>}
   */
  async get(id) {
    const { status, body } = await this.#request(
      "GET",
      `/tasks/${encodeURIComponent(id)}`,
    );
    if (status !== 200) throw taskError(status, id, body);
    return /** @type {Task} */ (body);
  }

  /**
   * @param {{done?: boolean}} [options]
   * @returns {Promise<Task[]>}
   */
  async list({ done } = {}) {
    const path = done === undefined ? "/tasks" : `/tasks?done=${done}`;
    const { status, body } = await this.#request("GET", path);
    if (status !== 200) throw taskError(status, undefined, body);
    return /** @type {Task[]} */ (body ?? []);
  }

  /**
   * Partial update — only fields present in `fields` change.
   * @param {string} id
   * @param {TaskUpdateFields} [fields]
   * @returns {Promise<Task>}
   */
  async update(id, fields = {}) {
    const { status, body } = await this.#request(
      "PATCH",
      `/tasks/${encodeURIComponent(id)}`,
      fields,
    );
    if (status !== 200) throw taskError(status, id, body);
    return /** @type {Task} */ (body);
  }

  /**
   * @param {string} id
   * @returns {Promise<void>}
   */
  async delete(id) {
    const { status, body } = await this.#request(
      "DELETE",
      `/tasks/${encodeURIComponent(id)}`,
    );
    if (status !== 204) throw taskError(status, id, body);
  }

  /**
   * Applies each item's update independently. An item with an unknown
   * `id` fails on its own (recorded in the result's `failed` array)
   * without aborting the batch — the returned promise only rejects for
   * a whole-call failure (network error, malformed request), never for
   * a per-item not-found. allSettled-style: the caller always gets both
   * lists back, never a partial-failure exception.
   * @param {BulkUpdateItem[]} items
   * @returns {Promise<BulkUpdateResult>}
   */
  async bulkUpdate(items) {
    const { status, body } = await this.#request("POST", "/tasks/bulk_update", {
      items,
    });
    if (status !== 200) throw taskError(status, undefined, body);
    return {
      succeeded: body?.succeeded ?? [],
      failed: (body?.failed ?? []).map((f) => ({ id: f.id, error: f.error })),
    };
  }
}
