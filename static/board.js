'use strict';

const RUNE = ['I', 'II', 'III', 'IV', 'V', 'VI'];
const GROUP_ICON = { music: '🎵', ambiance: '🌿', effects: '⚡' };

let activeGroup = 'music';
let activeSlot = null;
let config = null;
const library = {};

// Panel-local editing state — discarded on cancel
let pendingTracks = null;  // music only: copy of tracks being edited
let pendingPath = null;    // ambiance/effects only: selected file path

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  const resp = await apiFetch('/api/config');
  if (!resp) return;
  config = await resp.json();
  renderButtons();
}

// ── Rendering ─────────────────────────────────────────────────────────────────

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

function hasSound(slotIndex) {
  if (!config || !activeGroup) return false;
  const slot = config.sounds[activeGroup][slotIndex];
  if (activeGroup === 'music') return Array.isArray(slot) && slot.length > 0;
  return !!slot;
}

function getSubText(slotIndex) {
  const slot = config.sounds[activeGroup][slotIndex];
  if (activeGroup === 'music') {
    const n = Array.isArray(slot) ? slot.length : 0;
    return n === 1 ? '1 track' : `${n} tracks`;
  }
  return slot ? slot.split('/').pop() : '';
}

// ── Interaction ───────────────────────────────────────────────────────────────

function selectGroup(group) {
  activeGroup = group;
  renderButtons();
  if (activeSlot !== null) renderPanel();
}

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

function renderPanel() {
  const panel = document.getElementById('config-panel');
  panel.hidden = false;

  const groupName = activeGroup.charAt(0).toUpperCase() + activeGroup.slice(1);
  document.getElementById('panel-title').textContent = `Rune ${RUNE[activeSlot]} — ${groupName}`;
  document.getElementById('panel-badge').textContent = `${GROUP_ICON[activeGroup]} ${groupName}`;
  document.getElementById('label-input').value = config.button_labels[activeSlot];

  const container = document.getElementById('panel-content');
  if (activeGroup === 'music') {
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
        <option value="__upload__">Upload new file…</option>
      </select>
    </div>
    <input type="file" id="upload-input" accept=".ogg,.mp3,.wav" style="display:none" onchange="onUpload('music')">
  `;
}

function renderSingleContent(container) {
  container.innerHTML = `
    <div class="field-label">Sound file</div>
    <select class="field-select" id="single-library-select" onchange="onSingleSelect(this)">
      <option value="">— none —</option>
      <option value="__upload__">Upload new file…</option>
    </select>
    <input type="file" id="upload-input" accept=".ogg,.mp3,.wav" style="display:none" onchange="onUpload('${activeGroup}')">
  `;
}

// ── Library loading ───────────────────────────────────────────────────────────

async function loadLibrary(group) {
  if (library[group]) return library[group];
  const resp = await apiFetch(`/api/sounds/library/${group}`);
  if (!resp) return [];
  const data = await resp.json();
  library[group] = data.files;
  return library[group];
}

function populateMusicSelect(files) {
  const select = document.getElementById('music-library-select');
  if (!select) return;
  while (select.options.length > 2) select.remove(2);
  files.forEach(f => select.add(new Option(f.split('/').pop(), f)));
}

function populateSingleSelect(files, currentPath) {
  const select = document.getElementById('single-library-select');
  if (!select) return;
  while (select.options.length > 2) select.remove(2);
  files.forEach(f => {
    const opt = new Option(f.split('/').pop(), f);
    if (f === currentPath) opt.selected = true;
    select.add(opt);
  });
}

// ── Library interactions ──────────────────────────────────────────────────────

function toggleLibraryPicker() {
  const picker = document.getElementById('library-picker');
  if (picker) picker.style.display = picker.style.display === 'none' ? 'block' : 'none';
}

function onMusicLibrarySelect(select) {
  if (select.value === '__upload__') {
    select.value = '';
    document.getElementById('upload-input').click();
    return;
  }
  if (!select.value) return;
  const path = select.value;
  if (!pendingTracks.includes(path)) pendingTracks.push(path);
  select.value = '';
  renderMusicContent(document.getElementById('panel-content'));
  loadLibrary('music').then(populateMusicSelect);
}

function onSingleSelect(select) {
  if (select.value === '__upload__') {
    select.value = pendingPath || '';
    document.getElementById('upload-input').click();
    return;
  }
  pendingPath = select.value || null;
}

function removeTrack(index) {
  pendingTracks.splice(index, 1);
  renderMusicContent(document.getElementById('panel-content'));
  loadLibrary('music').then(populateMusicSelect);
}

// ── File upload ───────────────────────────────────────────────────────────────

async function onUpload(group) {
  const input = document.getElementById('upload-input');
  const file = input.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append('file', file);
  const resp = await apiFetch(`/api/upload/${group}`, { method: 'POST', body: formData });
  if (!resp) { input.value = ''; return; }
  const data = await resp.json();
  delete library[group];
  showToast(`Uploaded: ${file.name}`, 'success');
  input.value = '';
  if (group === 'music') {
    pendingTracks.push(data.path);
    const files = await loadLibrary(group);
    renderMusicContent(document.getElementById('panel-content'));
    populateMusicSelect(files);
  } else {
    pendingPath = data.path;
    const files = await loadLibrary(group);
    populateSingleSelect(files, pendingPath);
  }
}

// ── Save / Cancel ─────────────────────────────────────────────────────────────

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

function cancelSlot() {
  closePanel();
}

function closePanel() {
  activeSlot = null;
  pendingTracks = null;
  pendingPath = null;
  document.getElementById('config-panel').hidden = true;
  renderButtons();
}

// ── Restart ───────────────────────────────────────────────────────────────────

async function restartDevice() {
  await apiFetch('/api/restart', { method: 'POST' });
  showToast('Awakening the machine…', 'info');
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function esc(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

document.addEventListener('DOMContentLoaded', init);
