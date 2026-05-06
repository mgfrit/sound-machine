'use strict';

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

function showToast(message, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = message;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}
