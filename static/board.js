'use strict';

// Rune names shown in the panel title (e.g. "Rune III — Music")
const RUNE = ['I', 'II', 'III', 'IV', 'V', 'VI'];

// Icons displayed next to the group name in the panel badge
const GROUP_ICON = { music: '🎵', ambiance: '🌿', effects: '⚡' };

// ── Page state ────────────────────────────────────────────────────────────────
// These variables track what the user has selected and what is being edited.
// They are module-level (not inside a class) because this is the only JS file
// on the board page.

let activeGroup = 'music';   // Which group button (top row) is currently lit
let activeSlot = null;       // Which rune dome (0–5) is open for editing, or null
let config = null;           // Full config object fetched from /api/config

// Per-group file lists fetched on demand and cached here so we don't re-fetch
// every time the user opens a slot panel.
const library = {};

// Panel-local editing state — these hold the user's unsaved changes while the
// config panel is open. Discarded on cancel, committed to the server on save.
let pendingTracks = null;  // music only: copy of the playlist being edited
let pendingPath = null;    // ambiance/effects only: the selected file path

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  // Fetch the full config once on page load, then render the board.
  const resp = await apiFetch('/api/config');
  if (!resp) return;
  config = await resp.json();
  renderButtons();
}

// ── Rendering ─────────────────────────────────────────────────────────────────

/**
 * Sync every button's visual state to the current JS variables.
 * Called after any state change: group switch, slot select/deselect, save/cancel.
 *
 * Group buttons: highlights the active group with the 'active' CSS class.
 * Rune domes: each dome shows either a label + sub-text (if a sound is assigned)
 *   or "dormant" (empty slot). The 'selected' class opens the dome visually;
 *   'has-sound' dims the dome slightly to show it has content but isn't selected.
 */
function renderButtons() {
  for (const g of ['music', 'ambiance', 'effects']) {
    document.querySelector(`.btn-${g}`).classList.toggle('active', g === activeGroup);
  }
  for (let i = 0; i < 6; i++) {
    const el = document.querySelector(`[data-slot="${i}"]`);
    const hasSnd = hasSound(i);
    const isSelected = activeSlot === i;

    el.classList.toggle('selected', isSelected);
    el.classList.toggle('has-sound', hasSnd && !isSelected);

    const labelEl = el.querySelector('.dome-slot-label');
    const subEl = el.querySelector('.dome-slot-sub');

    if (hasSnd) {
      labelEl.textContent = config.button_labels[i];
      subEl.textContent = getSubText(i);
    } else {
      labelEl.textContent = 'dormant';
      subEl.textContent = '';
    }
  }
}

/**
 * Returns true if the given slot has at least one sound assigned for the active group.
 * Music slots are arrays (playlists), so we check length > 0.
 * Ambiance/effects slots are strings — any truthy value counts.
 */
function hasSound(slotIndex) {
  if (!config || !activeGroup) return false;
  const slot = config.sounds[activeGroup][slotIndex];
  if (activeGroup === 'music') return Array.isArray(slot) && slot.length > 0;
  return !!slot;
}

/**
 * Return the small subtitle shown inside a dome when it has a sound assigned.
 * Music: "1 track" or "N tracks" (playlist length).
 * Ambiance/effects: just the filename (without path prefix).
 */
function getSubText(slotIndex) {
  const slot = config.sounds[activeGroup][slotIndex];
  if (activeGroup === 'music') {
    const n = Array.isArray(slot) ? slot.length : 0;
    return n === 1 ? '1 track' : `${n} tracks`;
  }
  return slot ? slot.split('/').pop() : '';
}

// ── Interaction ───────────────────────────────────────────────────────────────

/**
 * Called when the user clicks a group button (Music / Ambiance / Effects).
 * Switches the active group and re-renders the board. If a slot panel is open,
 * re-renders that too so it shows the correct content for the new group.
 */
function selectGroup(group) {
  activeGroup = group;
  renderButtons();
  if (activeSlot !== null) renderPanel();
}

/**
 * Called when the user clicks a rune dome.
 * Clicking the already-selected slot closes the panel (toggle).
 * Clicking a different slot opens its panel.
 */
function selectSlot(index) {
  if (activeSlot === index) {
    closePanel();
    return;
  }
  activeSlot = index;
  renderButtons();
  renderPanel();
}

// ── Panel ─────────────────────────────────────────────────────────────────────

/**
 * Build and show the config panel for the currently selected slot.
 *
 * The panel title and badge reflect the active slot (Rune I–VI) and group.
 * The panel body differs by group:
 *   Music    — a playlist editor with an "Add track" button and library picker
 *   Ambiance — a single-file selector dropdown
 *   Effects  — a single-file selector dropdown
 *
 * pendingTracks / pendingPath hold the user's in-progress changes until save or cancel.
 */
function renderPanel() {
  const panel = document.getElementById('config-panel');
  panel.hidden = false;

  const groupName = activeGroup.charAt(0).toUpperCase() + activeGroup.slice(1);
  document.getElementById('panel-title').textContent = `Rune ${RUNE[activeSlot]} — ${groupName}`;
  document.getElementById('panel-badge').textContent = `${GROUP_ICON[activeGroup]} ${groupName}`;
  document.getElementById('label-input').value = config.button_labels[activeSlot];

  const container = document.getElementById('panel-content');
  if (activeGroup === 'music') {
    // Copy the playlist so edits don't mutate config until the user saves
    pendingTracks = [...(config.sounds.music[activeSlot] || [])];
    pendingPath = null;
    renderMusicContent(container);
    loadLibrary('music').then(populateMusicSelect);
  } else {
    pendingPath = config.sounds[activeGroup][activeSlot] || null;
    pendingTracks = null;
    renderSingleContent(container);
    loadLibrary(activeGroup).then(files => populateSingleSelect(files, pendingPath));
  }
}

/**
 * Render the music panel body: a scrollable playlist with remove buttons
 * and an expandable "Add track from library" section.
 */
function renderMusicContent(container) {
  const trackRows = pendingTracks.map((path, i) => {
    const name = esc(path.split('/').pop());
    return `<div class="track-row">
      <span class="track-name">${name}</span>
      <button class="track-remove" onclick="removeTrack(${i})">✕</button>
    </div>`;
  }).join('');

  const emptyMsg = pendingTracks.length === 0
    ? '<p style="color:#4a3820;font-size:13px;margin-bottom:8px;font-style:italic">No tracks added yet.</p>'
    : '';

  container.innerHTML = `
    <div class="field-label">Playlist — plays sequentially, fading between tracks</div>
    <div class="playlist" id="track-list">${emptyMsg}${trackRows}</div>
    <button class="btn-add" onclick="toggleLibraryPicker()">✦ Add track from library</button>
    <div id="library-picker" style="display:none">
      <div class="field-label">Pick a track to add</div>
      <select class="field-select" id="music-library-select" onchange="onMusicLibrarySelect(this)">
        <option value="">— pick a track —</option>
      </select>
    </div>
  `;
}

/**
 * Render the ambiance/effects panel body: a single dropdown for choosing one file.
 */
function renderSingleContent(container) {
  container.innerHTML = `
    <div class="field-label">Sound file</div>
    <select class="field-select" id="single-library-select" onchange="onSingleSelect(this)">
      <option value="">— none —</option>
    </select>
  `;
}

// ── Library loading ───────────────────────────────────────────────────────────

/**
 * Fetch the list of available files for a group from the server.
 * Results are cached in the module-level `library` object so each group
 * is only fetched once per page load. Returns the file list.
 */
async function loadLibrary(group) {
  if (library[group]) return library[group];
  const resp = await apiFetch(`/api/sounds/library/${group}`);
  if (!resp) return [];
  const data = await resp.json();
  library[group] = data.files;
  return library[group];
}

/**
 * Return the user-facing display name for a file path.
 * Looks up config.file_labels (set via the Library page), falls back to the filename.
 */
function fileLabel(path) {
  return (config.file_labels || {})[path] || path.split('/').pop();
}

/**
 * Populate the music "Add track" dropdown with all available files.
 * Keeps the first placeholder option, removes old file options, adds fresh ones.
 */
function populateMusicSelect(files) {
  const select = document.getElementById('music-library-select');
  if (!select) return;
  while (select.options.length > 2) select.remove(2);
  files.forEach(f => select.add(new Option(fileLabel(f), f)));
}

/**
 * Populate the ambiance/effects file dropdown.
 * The currently assigned file (currentPath) is pre-selected.
 */
function populateSingleSelect(files, currentPath) {
  const select = document.getElementById('single-library-select');
  if (!select) return;
  while (select.options.length > 2) select.remove(2);
  files.forEach(f => {
    const opt = new Option(fileLabel(f), f);
    if (f === currentPath) opt.selected = true;
    select.add(opt);
  });
}

// ── Library interactions ──────────────────────────────────────────────────────

/** Show/hide the "Add track from library" dropdown in the music panel. */
function toggleLibraryPicker() {
  const picker = document.getElementById('library-picker');
  if (picker) picker.style.display = picker.style.display === 'none' ? 'block' : 'none';
}

/**
 * Called when the user picks a track from the music library dropdown.
 * Adds the track to pendingTracks if it isn't already in the playlist.
 * Auto-fills the slot label from the file's display name if this is the first track added.
 * Resets the dropdown to placeholder and re-renders the track list.
 */
function onMusicLibrarySelect(select) {
  if (!select.value) return;
  const path = select.value;
  if (!pendingTracks.includes(path)) pendingTracks.push(path);
  if (pendingTracks.length === 1) {
    document.getElementById('label-input').value = fileLabel(path);
  }
  select.value = '';
  renderMusicContent(document.getElementById('panel-content'));
  loadLibrary('music').then(populateMusicSelect);
}

/**
 * Called when the user picks a file from the ambiance/effects dropdown.
 * Updates pendingPath and auto-fills the slot label from the file's display name.
 */
function onSingleSelect(select) {
  pendingPath = select.value || null;
  if (pendingPath) {
    document.getElementById('label-input').value = fileLabel(pendingPath);
  }
}

/** Remove a track from the pending playlist by its index and re-render. */
function removeTrack(index) {
  pendingTracks.splice(index, 1);
  renderMusicContent(document.getElementById('panel-content'));
  loadLibrary('music').then(populateMusicSelect);
}

// ── Save / Cancel ─────────────────────────────────────────────────────────────

/**
 * Save the current panel's changes to the server.
 *
 * Always saves the slot label first (PUT /api/config/label/:index).
 * Then saves the sound assignment:
 *   Music    — PUT /api/sounds/music/:index with the pending playlist
 *   Ambiance — PUT /api/sounds/ambiance/:index with the pending file path
 *   Effects  — PUT /api/sounds/effects/:index with the pending file path
 *
 * Updates config in memory after each successful save so the board re-renders
 * correctly without needing a full page reload.
 */
async function saveSlot() {
  const label = document.getElementById('label-input').value.trim();
  if (!label) { showToast('Label cannot be empty', 'error'); return; }

  const labelResp = await apiFetch(`/api/config/label/${activeSlot}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label }),
  });
  if (!labelResp) return;
  config.button_labels[activeSlot] = label;

  if (activeGroup === 'music') {
    const paths = pendingTracks.length > 0 ? pendingTracks : null;
    const resp = await apiFetch(`/api/sounds/music/${activeSlot}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paths }),
    });
    if (!resp) return;
    config.sounds.music[activeSlot] = paths;
  } else {
    const path = pendingPath || null;
    const resp = await apiFetch(`/api/sounds/${activeGroup}/${activeSlot}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path }),
    });
    if (!resp) return;
    config.sounds[activeGroup][activeSlot] = path;
  }

  showToast('Inscribed!', 'success');
  closePanel();
}

/** Discard pending changes and close the panel without saving. */
function cancelSlot() {
  closePanel();
}

/**
 * Close the config panel and clear all editing state.
 * renderButtons() is called to un-highlight the previously selected dome.
 */
function closePanel() {
  activeSlot = null;
  pendingTracks = null;
  pendingPath = null;
  document.getElementById('config-panel').hidden = true;
  renderButtons();
}

// ── Restart ───────────────────────────────────────────────────────────────────

/**
 * Restart the main sound-machine service (GPIO buttons and audio engine).
 * This is needed after config changes so the physical buttons pick up the
 * new settings. The web app itself keeps running.
 */
async function restartDevice() {
  await apiFetch('/api/restart', { method: 'POST' });
  showToast('Awakening the machine…', 'info');
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Escape a string for safe insertion into HTML text content.
 * Prevents user-provided filenames from being interpreted as HTML tags.
 */
function esc(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

document.addEventListener('DOMContentLoaded', init);
