/**
 * Typed errors for the Tasks API client, per core/mock-api/contract.md's
 * "Not found" and "Invalid input" cases.
 */

/**
 * Thrown by get/update/delete when `id` doesn't match any stored task.
 * `body` carries the backend's raw parsed JSON error response, so a
 * caller (e.g. the QC server) can proxy it through unchanged rather than
 * re-deriving its own error wording.
 */
export class TaskNotFoundError extends Error {
  /**
   * @param {string|undefined} id
   * @param {*} body
   */
  constructor(id, body) {
    super(`task not found: ${id}`);
    this.name = "TaskNotFoundError";
    this.taskId = id;
    this.body = body;
  }
}

/**
 * Thrown by create/update when a supplied field fails its type/format
 * requirement (e.g. missing `title`, malformed `due_date`). `body`
 * carries the backend's raw parsed JSON error response, same reasoning
 * as TaskNotFoundError.
 */
export class TaskValidationError extends Error {
  /**
   * @param {*} body
   */
  constructor(body) {
    super("invalid input");
    this.name = "TaskValidationError";
    this.body = body;
  }
}
