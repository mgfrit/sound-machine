'use strict';

// ── API helpers ───────────────────────────────────────────────────────────────
// Shared by board.js and library.js via a <script> tag in each HTML page.

/**
 * Wrapper around fetch() that centralises error handling for all API calls.
 *
 * On network failure: shows a "Network error" toast and returns null.
 * On non-2xx HTTP response: reads the JSON body for an "error" field,
 *   shows it as a toast, and returns null.
 * On success: returns the raw Response object so the caller can call .json().
 *
 * Callers check `if (!resp) return;` to bail out on failure without
 * needing any error handling of their own.
 */
async function apiFetch(url, options = {}) {
  try {
    const resp = await fetch(url, options);
    if (!resp.ok) {
      let msg = `Error ${resp.status}`;
      try { const d = await resp.json(); msg = d.error || msg; } catch (_) {}
      showToast(msg, 'error');
      return null;
    }
    return resp;
  } catch (_) {
    showToast('Network error — check connection', 'error');
    return null;
  }
}

/**
 * Show a brief, self-dismissing notification in the bottom-right corner.
 *
 * type controls the colour via the CSS class `toast-{type}`:
 *   'success' — green
 *   'error'   — red
 *   'info'    — neutral (default)
 *
 * The element removes itself after 3 seconds. Styles are in styles.css.
 */
function showToast(message, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}
