# Sound Library — Design Spec

**Date:** 2026-05-06
**Status:** Approved

## Overview

Add a new "Library" tab to the Sound Machine web app for managing all uploaded sound files across all three groups (Music, Ambiance, Effects). The library provides file upload, per-file display labels, in-browser audio preview, rename, and delete. Renaming a file label cascades to any button slots on the main board whose label still matches the old value.

## Data Model

A new `file_labels` dict is added to `config.json`, mapping file path → display label:

```json
"file_labels": {
  "sounds/music/Spikeroog.ogg": "Spikeroog",
  "sounds/ambiance/rainfall.ogg": "Rainfall",
  "sounds/effects/sword.wav": "Sword Strike"
}
```

- **Default label on upload:** filename with extension stripped and underscores/hyphens replaced by spaces (e.g. `battle_march.wav` → `"battle march"`).
- **Migration:** `_migrate_config()` initializes `file_labels: {}` if the key is absent.
- **Config API:** `GET /api/config` is extended to include `file_labels` in its response so `board.js` can access labels when the user opens the Inscribe panel.

## Backend

### New routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/library` | Serves `library.html` |
| GET | `/sounds/<path:filename>` | Serves sound files from the `sounds/` directory for browser audio preview. Required because `sounds/` is not inside Flask's `static_folder`. |

### New API endpoints

**`GET /api/library`**
Returns all three groups' files with their labels and current slot assignments.

```json
{
  "music": [
    {
      "path": "sounds/music/Spikeroog.ogg",
      "label": "Spikeroog",
      "slots": [{"group": "music", "index": 0, "rune": "Rune I"}]
    }
  ],
  "ambiance": [...],
  "effects": [...]
}
```

**`PUT /api/library/label`**
Body: `{"path": "sounds/music/Spikeroog.ogg", "label": "Dragon Lair"}`

1. Reads the old label from `file_labels[path]`.
2. Updates `file_labels[path]` to the new label.
3. Scans all `button_labels` slots — any slot whose label exactly matches the old label is updated to the new label.
4. Returns `{"ok": true, "updated_slots": [0, 1]}`.

**`DELETE /api/library/file?path=<encoded-path>`**
Query param: `path=sounds/music/foo.wav`

1. Deletes the file from disk.
2. Clears all `config.sounds` slots referencing this path: sets non-music slots to `null`; removes the path from music playlist arrays (sets slot to `null` if the playlist becomes empty).
3. Removes the entry from `file_labels`.
4. Returns `{"ok": true, "cleared_slots": [{"group": "music", "index": 0}]}`.

### Modified endpoint

**`POST /api/upload/<group>`** — existing behavior unchanged, extended to write a default label into `file_labels` for the uploaded file.

## Frontend — Library Page

### Files

- `static/library.html` — page shell with nav and script tags
- `static/library.js` — all page logic

### Layout

Three tabs at the top: **🎵 Music** | **🌿 Ambiance** | **⚡ Effects**. Switching tabs shows only that group's files.

Each tab contains:

**Upload bar**
- "Upload File" button → triggers hidden `<input type="file" accept=".wav,.ogg,.mp3">` → POSTs to `/api/upload/<group>` → refreshes file list.

**File table** — columns: Label | Filename | Assigned to | Actions

- **Label:** display name from `file_labels`. Clicking "Rename" replaces it with an inline `<input>`; "Save" calls `PUT /api/library/label` then re-renders.
- **Filename:** raw filename shown below the label in greyed, smaller text.
- **Assigned to:** chips showing rune slot names (e.g. "Rune I") for every slot currently mapped to this file. Empty string if unassigned.
- **Actions:**
  - **▶ Play** — loads the file's static URL into the shared `<audio>` element and plays it. The button changes to "▶ Playing" while active; clicking another row's Play stops the previous track.
  - **✎ Rename** — toggles inline edit mode for the label.
  - **🗑 Delete** — if the file is assigned to any slots, shows a confirmation dialog listing affected runes before proceeding. On confirm, calls `DELETE /api/library/file`.

**Audio player** (pinned at bottom of panel)
- Native HTML `<audio controls>` element.
- Plays through the browser/device — not through the Raspberry Pi's audio output or Bluetooth speaker.
- Shows the currently-previewing file name.

### Navigation

"Library" link added to the `<nav>` in `index.html`, `wifi.html`, and `instructions.html`. Styled consistently with the existing nav links; marked `class="active"` only on `library.html`.

## Board Integration

### `board.js` changes

- **`GET /api/config` response** now includes `file_labels`; `board.js` stores it in the local `config` object.
- **Inscribe panel auto-fill:** when the user picks a file from the dropdown, the "Button Label" field auto-populates with `config.file_labels[path]` (falling back to the filename without extension if no label exists). The user may edit it before clicking Inscribe. Saving writes to `button_labels[slot]` as before.

### What does not change

- The board dome continues to render `button_labels[slot]`. File labels flow into slot labels naturally through the Inscribe auto-fill and the rename cascade — no separate dome rendering path needed.
- All existing Inscribe, save, and restart flows are unchanged.

## Error Handling

- Upload: server rejects unsupported extensions with a 400 and a toast on the page.
- Delete of a missing file: server returns 404; page shows a toast.
- Rename to empty string: rejected client-side before the API call.
- Delete while assigned: client-side confirmation dialog before the API call; server also clears slots defensively regardless.

## Out of Scope

- Drag-and-drop upload (file picker only).
- Sorting or searching the file list.
- Batch delete.
- Moving files between groups.
