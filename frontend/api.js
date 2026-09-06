/*
 * api.js — API access layer for the Workshop Feedback Portal.
 *
 * This module isolates all network/API concerns from the DOM/event code in
 * app.js. It implements the exact request/response shapes defined in
 * docs/api-contract.md:
 *
 *   POST /feedback   (attendee submission, no auth)
 *   GET  /feedback   (organizer review, X-Organizer-Key header)
 *
 * Design notes:
 *  - The API base URL comes from window.APP_CONFIG.apiBaseUrl (config.js),
 *    which is a non-secret Terraform output. Nothing here is hardcoded to an
 *    account-specific URL and no secret is embedded (NFR-007, AC-013).
 *  - Error responses are NOT assumed to be valid JSON (contract section 1).
 *  - All results are returned as plain data objects; rendering is app.js's job.
 */
(function (global) {
  "use strict";

  /**
   * Resolve and normalize the configured API base URL.
   * @returns {string} base URL without a trailing slash
   * @throws {Error} if the base URL is missing or still a placeholder
   */
  function getApiBaseUrl() {
    var cfg = global.APP_CONFIG || {};
    var base = (cfg.apiBaseUrl || "").trim();
    if (!base || base.indexOf("__API_BASE_URL__") !== -1) {
      throw new Error(
        "API base URL is not configured. Set apiBaseUrl in config.js."
      );
    }
    return base.replace(/\/+$/, "");
  }

  /**
   * Attempt to parse a response body as JSON, tolerating empty/invalid bodies.
   * @param {Response} response
   * @returns {Promise<any|null>}
   */
  function safeParseJson(response) {
    return response.text().then(function (text) {
      if (!text) {
        return null;
      }
      try {
        return JSON.parse(text);
      } catch (e) {
        return null;
      }
    });
  }

  /**
   * Extract a human-safe error message from a parsed error body, per the
   * standard error shape { error: { code, message, details } }.
   * Falls back to a generic, status-appropriate message.
   * @param {any} body
   * @param {number} status
   * @returns {{ code: string, message: string, details: Array }}
   */
  function normalizeError(body, status) {
    var fallback = {
      code: "UNKNOWN_ERROR",
      message: "Something went wrong. Please try again.",
      details: []
    };

    if (body && body.error && typeof body.error === "object") {
      return {
        code: typeof body.error.code === "string" ? body.error.code : fallback.code,
        message:
          typeof body.error.message === "string" && body.error.message
            ? body.error.message
            : fallback.message,
        details: Array.isArray(body.error.details) ? body.error.details : []
      };
    }

    // No structured error body (e.g., non-JSON 5xx or network edge case).
    if (status >= 500) {
      return {
        code: "INTERNAL_ERROR",
        message: "The server encountered an error. Please try again later.",
        details: []
      };
    }
    return fallback;
  }

  /**
   * Submit a feedback record. Maps to POST /feedback.
   * @param {{ workshopId: string, rating: number, comment?: string }} payload
   * @returns {Promise<{ ok: boolean, status: number, data?: object, error?: object }>}
   */
  function submitFeedback(payload) {
    var url = getApiBaseUrl() + "/feedback";
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(function (response) {
      return safeParseJson(response).then(function (body) {
        if (response.status === 201) {
          return { ok: true, status: 201, data: body || {} };
        }
        return {
          ok: false,
          status: response.status,
          error: normalizeError(body, response.status)
        };
      });
    });
  }

  /**
   * List feedback for organizer review. Maps to GET /feedback.
   * @param {string} organizerKey — sent as the X-Organizer-Key header
   * @returns {Promise<{ ok: boolean, status: number, data?: {items: Array, count: number}, error?: object }>}
   */
  function listFeedback(organizerKey) {
    var url = getApiBaseUrl() + "/feedback";
    return fetch(url, {
      method: "GET",
      headers: { "X-Organizer-Key": organizerKey }
    }).then(function (response) {
      return safeParseJson(response).then(function (body) {
        if (response.status === 200) {
          var items = body && Array.isArray(body.items) ? body.items : [];
          var count =
            body && typeof body.count === "number" ? body.count : items.length;
          return { ok: true, status: 200, data: { items: items, count: count } };
        }
        return {
          ok: false,
          status: response.status,
          error: normalizeError(body, response.status)
        };
      });
    });
  }

  global.FeedbackApi = {
    getApiBaseUrl: getApiBaseUrl,
    submitFeedback: submitFeedback,
    listFeedback: listFeedback
  };
})(window);
