/*
 * app.js — DOM and event logic for the Workshop Feedback Portal.
 *
 * Responsibilities:
 *  - Tab switching between the attendee submission view and organizer review view.
 *  - Client-side convenience validation that MIRRORS the server rules in
 *    docs/api-contract.md (server remains authoritative — BR-008).
 *  - Managing UI states: IDLE, LOADING, SUCCESS, ERROR, EMPTY.
 *  - Rendering all untrusted API/user data with textContent (no innerHTML).
 *
 * Validation rules mirrored from the contract:
 *  - workshopId: required, non-empty after trim, max 200 chars.
 *  - rating: required integer 1..5.
 *  - comment: optional, max 1000 chars when present.
 */
(function () {
  "use strict";

  var WORKSHOP_ID_MAX = 200;
  var COMMENT_MAX = 1000;
  var RATING_MIN = 1;
  var RATING_MAX = 5;

  /** Cache DOM references once the document is ready. */
  var els = {};

  document.addEventListener("DOMContentLoaded", function () {
    cacheElements();
    buildRatingOptions();
    wireTabs();
    wireSubmissionForm();
    wireReviewForm();
    wireCommentCounter();
  });

  function cacheElements() {
    els.tabSubmit = document.getElementById("tab-submit");
    els.tabReview = document.getElementById("tab-review");
    els.panelSubmit = document.getElementById("panel-submit");
    els.panelReview = document.getElementById("panel-review");

    els.feedbackForm = document.getElementById("feedback-form");
    els.workshopId = document.getElementById("workshopId");
    els.workshopIdError = document.getElementById("workshopId-error");
    els.ratingOptions = document.querySelector(".rating-options");
    els.ratingError = document.getElementById("rating-error");
    els.comment = document.getElementById("comment");
    els.commentError = document.getElementById("comment-error");
    els.commentCount = document.getElementById("comment-count");
    els.submitBtn = document.getElementById("submit-btn");
    els.submitSpinner = document.getElementById("submit-spinner");
    els.submitStatus = document.getElementById("submit-status");

    els.reviewForm = document.getElementById("review-form");
    els.organizerKey = document.getElementById("organizerKey");
    els.loadBtn = document.getElementById("load-btn");
    els.reviewSpinner = document.getElementById("review-spinner");
    els.reviewStatus = document.getElementById("review-status");
    els.reviewResults = document.getElementById("review-results");
  }

  /* ------------------------------- Tabs ------------------------------- */

  function wireTabs() {
    els.tabSubmit.addEventListener("click", function () {
      activateTab("submit");
    });
    els.tabReview.addEventListener("click", function () {
      activateTab("review");
    });
  }

  function activateTab(which) {
    var submitActive = which === "submit";
    els.tabSubmit.classList.toggle("is-active", submitActive);
    els.tabReview.classList.toggle("is-active", !submitActive);
    els.tabSubmit.setAttribute("aria-selected", String(submitActive));
    els.tabReview.setAttribute("aria-selected", String(!submitActive));
    els.panelSubmit.hidden = !submitActive;
    els.panelReview.hidden = submitActive;
  }

  /* --------------------------- Rating radios --------------------------- */

  function buildRatingOptions() {
    for (var i = RATING_MIN; i <= RATING_MAX; i++) {
      var id = "rating-" + i;

      var wrapper = document.createElement("label");
      wrapper.className = "rating-option";
      wrapper.setAttribute("for", id);

      var input = document.createElement("input");
      input.type = "radio";
      input.name = "rating";
      input.id = id;
      input.value = String(i);

      var text = document.createElement("span");
      text.textContent = String(i);

      wrapper.appendChild(input);
      wrapper.appendChild(text);
      els.ratingOptions.appendChild(wrapper);
    }
  }

  function getSelectedRating() {
    var checked = els.ratingOptions.querySelector('input[name="rating"]:checked');
    return checked ? parseInt(checked.value, 10) : null;
  }

  /* --------------------------- Comment counter -------------------------- */

  function wireCommentCounter() {
    updateCommentCount();
    els.comment.addEventListener("input", updateCommentCount);
  }

  function updateCommentCount() {
    var len = els.comment.value.length;
    els.commentCount.textContent = len + " / " + COMMENT_MAX;
  }

  /* --------------------------- Submission form -------------------------- */

  function wireSubmissionForm() {
    els.feedbackForm.addEventListener("submit", function (event) {
      event.preventDefault();
      handleSubmit();
    });
  }

  function clearFieldError(errorEl, inputEl) {
    errorEl.textContent = "";
    errorEl.hidden = true;
    if (inputEl) {
      inputEl.removeAttribute("aria-invalid");
    }
  }

  function setFieldError(errorEl, inputEl, message) {
    errorEl.textContent = message;
    errorEl.hidden = false;
    if (inputEl) {
      inputEl.setAttribute("aria-invalid", "true");
    }
  }

  /**
   * Convenience client-side validation. Returns a payload object when valid,
   * or null when invalid (field errors are shown). Server remains authoritative.
   */
  function validateSubmission() {
    var valid = true;
    clearFieldError(els.workshopIdError, els.workshopId);
    clearFieldError(els.ratingError, null);
    clearFieldError(els.commentError, els.comment);

    var workshopId = els.workshopId.value.trim();
    if (!workshopId) {
      setFieldError(
        els.workshopIdError,
        els.workshopId,
        "Workshop identifier is required."
      );
      valid = false;
    } else if (workshopId.length > WORKSHOP_ID_MAX) {
      setFieldError(
        els.workshopIdError,
        els.workshopId,
        "Workshop identifier must be at most " + WORKSHOP_ID_MAX + " characters."
      );
      valid = false;
    }

    var rating = getSelectedRating();
    if (rating === null) {
      setFieldError(
        els.ratingError,
        null,
        "Please select a rating between 1 and 5."
      );
      valid = false;
    }

    var comment = els.comment.value;
    if (comment.length > COMMENT_MAX) {
      setFieldError(
        els.commentError,
        els.comment,
        "Comment must be at most " + COMMENT_MAX + " characters."
      );
      valid = false;
    }

    if (!valid) {
      return null;
    }

    // Build the exact request payload per the contract. Omit comment when empty.
    var payload = { workshopId: workshopId, rating: rating };
    if (comment.trim().length > 0) {
      payload.comment = comment;
    }
    return payload;
  }

  function setSubmitLoading(isLoading) {
    els.submitBtn.disabled = isLoading;
    els.submitSpinner.hidden = !isLoading;
    els.submitBtn.textContent = isLoading ? "Submitting…" : "Submit feedback";
  }

  function showStatus(regionEl, type, message) {
    regionEl.className = "status-region status-" + type;
    regionEl.textContent = message;
    regionEl.hidden = false;
  }

  function hideStatus(regionEl) {
    regionEl.hidden = true;
    regionEl.textContent = "";
  }

  /**
   * Apply server-returned field-level validation details to the relevant
   * inputs. Falls back to the top-level message for anything unmapped.
   */
  function applyServerFieldErrors(details) {
    var fieldMap = {
      workshopId: { errorEl: els.workshopIdError, inputEl: els.workshopId },
      rating: { errorEl: els.ratingError, inputEl: null },
      comment: { errorEl: els.commentError, inputEl: els.comment }
    };
    if (!Array.isArray(details)) {
      return;
    }
    details.forEach(function (detail) {
      if (!detail || typeof detail !== "object") {
        return;
      }
      var target = fieldMap[detail.field];
      if (target && typeof detail.issue === "string") {
        setFieldError(target.errorEl, target.inputEl, detail.issue);
      }
    });
  }

  function handleSubmit() {
    hideStatus(els.submitStatus);

    var payload = validateSubmission();
    if (!payload) {
      showStatus(
        els.submitStatus,
        "error",
        "Please fix the highlighted fields and try again."
      );
      return;
    }

    setSubmitLoading(true);

    FeedbackApi.submitFeedback(payload)
      .then(function (result) {
        if (result.ok) {
          var msg =
            (result.data && result.data.message) ||
            "Feedback submitted successfully.";
          showStatus(els.submitStatus, "success", msg);
          resetFormAfterSuccess();
        } else {
          handleSubmitError(result);
        }
      })
      .catch(function () {
        showStatus(
          els.submitStatus,
          "error",
          "Could not reach the server. Check your connection and try again."
        );
      })
      .then(function () {
        setSubmitLoading(false);
      });
  }

  function handleSubmitError(result) {
    var error = result.error || {};
    if (error.code === "VALIDATION_ERROR" && Array.isArray(error.details)) {
      applyServerFieldErrors(error.details);
    }
    showStatus(
      els.submitStatus,
      "error",
      error.message || "Your submission was not accepted. Please review and retry."
    );
  }

  function resetFormAfterSuccess() {
    els.feedbackForm.reset();
    updateCommentCount();
    clearFieldError(els.workshopIdError, els.workshopId);
    clearFieldError(els.ratingError, null);
    clearFieldError(els.commentError, els.comment);
  }

  /* ----------------------------- Review form ---------------------------- */

  function wireReviewForm() {
    els.reviewForm.addEventListener("submit", function (event) {
      event.preventDefault();
      handleLoadFeedback();
    });
  }

  function setReviewLoading(isLoading) {
    els.loadBtn.disabled = isLoading;
    els.reviewSpinner.hidden = !isLoading;
    els.loadBtn.textContent = isLoading ? "Loading…" : "Load feedback";
  }

  function handleLoadFeedback() {
    hideStatus(els.reviewStatus);
    clearResults();

    var key = els.organizerKey.value;
    if (!key) {
      showStatus(
        els.reviewStatus,
        "error",
        "Enter the organizer access key to load feedback."
      );
      return;
    }

    setReviewLoading(true);

    FeedbackApi.listFeedback(key)
      .then(function (result) {
        if (result.ok) {
          renderResults(result.data);
        } else {
          handleReviewError(result);
        }
      })
      .catch(function () {
        showStatus(
          els.reviewStatus,
          "error",
          "Could not reach the server. Check your connection and try again."
        );
      })
      .then(function () {
        setReviewLoading(false);
      });
  }

  function handleReviewError(result) {
    var error = result.error || {};
    var message = error.message;
    if (result.status === 401) {
      message = message || "Organizer key is required.";
    } else if (result.status === 403) {
      message = message || "The organizer key is not valid.";
    }
    showStatus(els.reviewStatus, "error", message || "Unable to load feedback.");
  }

  function clearResults() {
    els.reviewResults.textContent = "";
  }

  /**
   * Render the feedback collection. Handles the EMPTY state (count 0) and
   * renders each record's fields safely with textContent (untrusted data).
   */
  function renderResults(data) {
    clearResults();
    var items = data.items || [];
    var count = typeof data.count === "number" ? data.count : items.length;

    var summary = document.createElement("p");
    summary.className = "results-summary";
    summary.textContent =
      count === 1 ? "1 feedback record" : count + " feedback records";
    els.reviewResults.appendChild(summary);

    if (count === 0 || items.length === 0) {
      var empty = document.createElement("p");
      empty.className = "empty-state";
      empty.textContent = "No feedback has been submitted yet.";
      els.reviewResults.appendChild(empty);
      return;
    }

    var list = document.createElement("ul");
    list.className = "feedback-list";

    items.forEach(function (item) {
      list.appendChild(buildFeedbackCard(item));
    });

    els.reviewResults.appendChild(list);
  }

  /**
   * Build one feedback card. Every value comes from the API and is treated as
   * untrusted: rendered exclusively via textContent, never innerHTML.
   */
  function buildFeedbackCard(item) {
    var li = document.createElement("li");
    li.className = "feedback-card";

    var header = document.createElement("div");
    header.className = "feedback-card-header";

    var workshop = document.createElement("span");
    workshop.className = "feedback-workshop";
    workshop.textContent = safeString(item.workshopId, "(unknown workshop)");

    var rating = document.createElement("span");
    rating.className = "feedback-rating";
    var ratingValue = safeString(item.rating, "?");
    rating.textContent = "Rating: " + ratingValue + " / 5";

    header.appendChild(workshop);
    header.appendChild(rating);
    li.appendChild(header);

    var comment = document.createElement("p");
    comment.className = "feedback-comment";
    if (item.comment === null || item.comment === undefined || item.comment === "") {
      comment.classList.add("feedback-comment-empty");
      comment.textContent = "No comment provided.";
    } else {
      comment.textContent = safeString(item.comment, "");
    }
    li.appendChild(comment);

    var time = document.createElement("p");
    time.className = "feedback-time";
    time.textContent = "Submitted: " + safeString(item.createdAt, "unknown time");
    li.appendChild(time);

    return li;
  }

  /**
   * Coerce a possibly-missing/non-string value into a display string without
   * ever using unsafe rendering. Numbers are converted; null/undefined use the
   * provided fallback.
   */
  function safeString(value, fallback) {
    if (value === null || value === undefined) {
      return fallback;
    }
    if (typeof value === "string") {
      return value;
    }
    return String(value);
  }
})();
