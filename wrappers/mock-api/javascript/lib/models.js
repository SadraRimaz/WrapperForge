/**
 * JSDoc-only type definitions mirroring core/mock-api/contract.md's
 * Task resource and the bulk_update partial-failure shapes. No runtime
 * code — this module exists purely for editor/type-checking support.
 */

/**
 * @typedef {Object} Task
 * @property {string} id
 * @property {string} title
 * @property {boolean} done
 * @property {string} due_date - ISO 8601 date (YYYY-MM-DD).
 * @property {number} priority_score - Server-generated, [0, 100).
 * @property {string} created_at - ISO 8601 UTC datetime.
 */

/**
 * @typedef {Object} TaskUpdateFields
 * @property {string} [title]
 * @property {boolean} [done]
 * @property {string} [due_date]
 */

/**
 * @typedef {Object} BulkUpdateItem
 * @property {string} id
 * @property {TaskUpdateFields} fields
 */

/**
 * @typedef {Object} BulkUpdateFailure
 * @property {string} id
 * @property {string} error
 */

/**
 * @typedef {Object} BulkUpdateResult
 * @property {Task[]} succeeded
 * @property {BulkUpdateFailure[]} failed
 */

export {};
