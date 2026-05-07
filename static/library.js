'use strict';

// ── Page state ────────────────────────────────────────────────────────────────

let activeGroup = 'music';  // Which tab is currently visible (music/ambiance/effects)
let libraryData = {};       // Full library response from /api/library, keyed by group
let playingPath = null;     // Path of the file currently loaded in the audio player, or null

// ── Init & data loading ───────────────────────────────────────────────────────

async function init() {
  await loadLibrary();
}

/**
 * Fetch the full library from the server and render the active tab.
 * Called on page load and after any mutation (rename, delete, upload).
 * The server response is a dict with keys "music", "ambiance", "effects",
 * each containing an array of {path, label, slots} objects.
 */
async function loadLibrary() {
  const resp = await apiFetch('/api/library');
  if (!resp) return;
  libraryData = await resp.json();
  renderFiles(libraryData[activeGroup] || []);
}

// ── Tab switching ─────────────────────────────────────────────────────────────

/**
 * Switch the visible tab to the given group and re-render the file table.
 * Updates the 'active' CSS class on all tab buttons and re-renders the table body.
 */
function switchTab(group) {
  activeGroup = group;
  document.querySelectorAll('.lib-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.group === group);
  });
  renderFiles(libraryData[group] || []);
}

// ── Table rendering ───────────────────────────────────────────────────────────

/**
 * Render the file table for the given array of file objects.
 * If the array is empty, shows a placeholder row.
 * Otherwise builds one <tr> per file using fileRow().
 */
function renderFiles(files) {
  const tbody = document.getElementById('lib-tbody');
  if (!files.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="lib-empty">No files in this group yet.</td></tr>';
    return;
  }
  tbody.innerHTML = files.map(fileRow).join('');
}

/** Return just the filename from a full path like "sounds/music/battle.ogg". */
function basename(path) {
  return path.split('/').pop();
}

/**
 * Escape special HTML characters to prevent XSS when inserting user-supplied
 * strings (filenames, labels) into innerHTML.
 */
function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/**
 * Safely encode a JavaScript value for use inside an HTML onclick="..." attribute.
 *
 * The problem: onclick='foo("some/path.ogg")' breaks if the path contains double quotes.
 * JSON.stringify wraps the value in double quotes, which would terminate the attribute early.
 * Solution: esc() converts those inner " to &quot;, which HTML decodes back to " before
 * running the JS, so the function receives the correct string.
 *
 * Example: attr('sounds/music/foo.ogg') → &quot;sounds/music/foo.ogg&quot;
 */
function attr(val) {
  return esc(JSON.stringify(val));
}

/**
 * Build one table row for a file entry.
 *
 * Columns:
 *   1. Label (display name from file_labels)
 *   2. Filename (just the basename, no path)
 *   3. Slot badges — which rune slots this file is assigned to (e.g. "Rune II")
 *      or "—" if unassigned
 *   4. Actions: Play, Rename, Delete buttons
 *
 * The 'playing' class on the Play button turns it green while audio is playing.
 */
function fileRow(f) {
  const slotBadges = f.slots.length
    ? f.slots.map(s => `<span class="lib-slot-badge">${esc(s.rune)}</span>`).join('')
    : '<span class="lib-unassigned">—</span>';
  const isPlaying = playingPath === f.path;
  return `<tr data-path="${esc(f.path)}">
    <td><span class="lib-label-text">${esc(f.label)}</span></td>
    <td class="lib-filename">${esc(basename(f.path))}</td>
    <td>${slotBadges}</td>
    <td class="lib-actions">
      <button class="lib-action-btn${isPlaying ? ' playing' : ''}"
        onclick="playFile(${attr(f.path)}, ${attr(f.label)})">
        ${isPlaying ? '▶ Playing' : '▶ Play'}
      </button>
      <button class="lib-action-btn"
        onclick="startRename(${attr(f.path)}, ${attr(f.label)})">✎ Rename</button>
      <button class="lib-action-btn danger"
        onclick="deleteFile(${attr(f.path)}, ${attr(f.slots)})">🗑️</button>
    </td>
  </tr>`;
}

// ── Audio preview ─────────────────────────────────────────────────────────────

/**
 * Load and play a file in the pinned browser audio player at the bottom of the page.
 * Audio plays in the browser (through the device viewing the page), not the Bluetooth speaker.
 *
 * The /sounds/<path> Flask route serves files from the sounds/ directory.
 * Paths from the API are like "sounds/music/foo.ogg", so we prepend "/" to
 * get the full URL "/sounds/music/foo.ogg".
 *
 * Updates playingPath and re-renders the table so the Play button turns green.
 */
function playFile(path, label) {
  const audio = document.getElementById('audio-player');
  const player = document.getElementById('lib-player');
  playingPath = path;
  audio.src = '/' + path;
  audio.play();
  document.getElementById('player-name').textContent = label;
  player.hidden = false;
  renderFiles(libraryData[activeGroup] || []);
}

// ── Rename ────────────────────────────────────────────────────────────────────

/**
 * Switch a table row into inline rename mode.
 *
 * Replaces the label cell with a text input pre-filled with the current label,
 * and replaces the action buttons with Save/Cancel. Pressing Enter saves,
 * pressing Escape cancels (reloads the full table from the server).
 *
 * CSS.escape() is used to safely select the row by path in querySelector,
 * since paths can contain characters like '/' that would break a raw selector.
 */
function startRename(path, currentLabel) {
  const row = document.querySelector(`tr[data-path="${CSS.escape(path)}"]`);
  const labelCell = row.querySelector('td:first-child');
  const actionsCell = row.querySelector('.lib-actions');
  labelCell.innerHTML = `<input class="lib-label-input" id="rename-input"
    value="${esc(currentLabel)}" maxlength="64"
    onkeydown="if(event.key===&quot;Enter&quot;)saveRename(${attr(path)});if(event.key===&quot;Escape&quot;)loadLibrary()">`;
  actionsCell.innerHTML = `
    <button class="lib-action-btn save" onclick="saveRename(${attr(path)})">✓ Save</button>
    <button class="lib-action-btn" onclick="loadLibrary()">✕ Cancel</button>`;
  const input = document.getElementById('rename-input');
  input.focus();
  input.select();
}

/**
 * Save a renamed label to the server via PUT /api/library/label.
 * The server updates file_labels in config.json and cascades the change to any
 * button_labels slot that was showing the old label. After success, reloads
 * the full library so the table reflects the new name everywhere.
 */
async function saveRename(path) {
  const input = document.getElementById('rename-input');
  const newLabel = input.value.trim();
  if (!newLabel) { showToast('Label cannot be empty', 'error'); return; }
  const resp = await apiFetch('/api/library/label', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, label: newLabel }),
  });
  if (!resp) return;
  showToast('Label updated', 'success');
  await loadLibrary();
}

// ── Delete ────────────────────────────────────────────────────────────────────

/**
 * Delete a file from disk after a confirmation prompt.
 *
 * If the file is assigned to any rune slots, the confirmation message lists
 * which runes will be affected (e.g. "Rune II, Rune IV") so the user knows
 * what they're clearing. This uses the slots array already attached to each
 * file object in the library response.
 *
 * If the deleted file is currently playing in the browser audio player,
 * the player is paused and hidden.
 *
 * Calls DELETE /api/library/file?path=<encoded-path>. The server deletes the
 * file, clears it from all slot assignments, and removes its file_labels entry.
 */
async function deleteFile(path, slots) {
  const msg = slots.length
    ? `Delete "${basename(path)}"? It will be removed from: ${slots.map(s => s.rune).join(', ')}.`
    : `Delete "${basename(path)}" from disk?`;
  if (!confirm(msg)) return;
  const resp = await apiFetch('/api/library/file?path=' + encodeURIComponent(path), { method: 'DELETE' });
  if (!resp) return;
  if (playingPath === path) {
    document.getElementById('audio-player').pause();
    playingPath = null;
    document.getElementById('lib-player').hidden = true;
  }
  showToast('File deleted', 'success');
  await loadLibrary();
}

// ── Upload ────────────────────────────────────────────────────────────────────

/**
 * Trigger the hidden file input by clicking it programmatically.
 * This lets us style our own "Upload" button instead of showing the
 * browser's default file input appearance.
 */
function triggerUpload() {
  document.getElementById('file-input').click();
}

/**
 * Handle a file selected from the upload dialog.
 * Submits the file as multipart/form-data to POST /api/upload/<activeGroup>.
 * The server saves the file, creates a default display label, and returns
 * the saved path. On success, reloads the library to show the new file.
 */
async function handleUpload(input) {
  const file = input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  const resp = await apiFetch('/api/upload/' + activeGroup, { method: 'POST', body: form });
  input.value = '';  // Reset so the same file can be re-uploaded if needed
  if (!resp) return;
  showToast('Uploaded: ' + file.name, 'success');
  await loadLibrary();
}

document.addEventListener('DOMContentLoaded', init);
