'use strict';

let activeGroup = 'music';
let libraryData = {};
let playingPath = null;

async function init() {
  await loadLibrary();
}

async function loadLibrary() {
  const resp = await apiFetch('/api/library');
  if (!resp) return;
  libraryData = await resp.json();
  renderFiles(libraryData[activeGroup] || []);
}

function switchTab(group) {
  activeGroup = group;
  document.querySelectorAll('.lib-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.group === group);
  });
  renderFiles(libraryData[group] || []);
}

function renderFiles(files) {
  const tbody = document.getElementById('lib-tbody');
  if (!files.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="lib-empty">No files in this group yet.</td></tr>';
    return;
  }
  tbody.innerHTML = files.map(fileRow).join('');
}

function basename(path) {
  return path.split('/').pop();
}

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function attr(val) {
  return esc(JSON.stringify(val));
}

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
        onclick="deleteFile(${attr(f.path)}, ${attr(f.slots)})">🗑</button>
    </td>
  </tr>`;
}

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

function triggerUpload() {
  document.getElementById('file-input').click();
}

async function handleUpload(input) {
  const file = input.files[0];
  if (!file) return;
  const form = new FormData();
  form.append('file', file);
  const resp = await apiFetch('/api/upload/' + activeGroup, { method: 'POST', body: form });
  input.value = '';
  if (!resp) return;
  showToast('Uploaded: ' + file.name, 'success');
  await loadLibrary();
}

document.addEventListener('DOMContentLoaded', init);
