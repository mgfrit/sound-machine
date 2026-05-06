# Web UI Redesign — Design Spec
**Date:** 2026-05-06  
**Status:** Approved

---

## Overview

Redesign the Flask web UI from a single functional configuration page into a polished, mobile-responsive, D&D-themed multi-page app. The redesign adds:

- An instructions page explaining the soundboard, Bluetooth, and WiFi setup
- A 3×3 arcade-button grid mirroring the physical device layout
- Per-slot editable labels stored in config
- A music playlist editor (multiple sequential tracks per slot, fade between tracks)
- A file library picker for adding tracks/sounds to slots
- Consistent D&D visual theme (Cinzel font, gem-coloured arcade buttons, gold accents, dark parchment palette) across all pages

The Flask backend and hardware code (`main.py`, `button_handler.py`) change minimally. The bulk of the work is frontend HTML/CSS/JS and small additions to `web_app.py` and `audio_player.py`.

---

## Architecture

**Approach:** Multi-page static HTML. Flask continues to serve static files and provide a JSON API. No build step, no JS framework.

### File changes

| File | Change |
|---|---|
| `static/styles.css` | **New** — shared D&D theme styles, responsive layout |
| `static/utils.js` | **New** — shared `apiFetch` helper, toast notifications |
| `static/instructions.html` | **New** — "The Lore" instructions page |
| `static/index.html` | **Redesign** — D&D-themed board page |
| `static/board.js` | **New** — board page interactivity |
| `static/wifi.html` | **Restyle** — apply shared nav + D&D theme, keep all logic |
| `web_app.py` | **Extend** — three new API endpoints |
| `config.json` | **Schema update** — add `button_labels`; music slots become arrays |
| `audio_player.py` | **Extend** — sequential playlist playback |
| `button_handler.py` | **Minor** — call `play_music_playlist` instead of `play_music` |
| `main.py` | **Minor** — pass playlist arrays; poll for track-end event |

---

## Config Schema

### New field: `button_labels`

A 6-element array of user-editable strings, one per physical sound button slot. Defaults to `["Slot 1", ..., "Slot 6"]`.

```json
"button_labels": ["Battle Theme", "Tavern Vibes", "Slot 3", "Slot 4", "Slot 5", "Slot 6"]
```

### Music slots: string → array

Music sound slots change from a single path (or `null`) to an array of paths (or `null`). Single-track slots are a one-element array. `null` means the slot is unassigned.

```json
"sounds": {
  "music": [
    ["sounds/music/Spikeroog.ogg", "sounds/music/battle_intro.ogg"],
    ["sounds/music/tavern.ogg"],
    null, null, null, null
  ],
  "ambiance": ["sounds/ambiance/rainfall.ogg", null, null, null, null, null],
  "effects":  ["sounds/effects/sword.wav",    null, null, null, null, null]
}
```

Ambiance and effects slots remain single strings (or `null`).

**Auto-migration:** On startup `web_app.py` checks each music slot. If it finds a bare string it wraps it in a list. This makes existing `config.json` files load without manual editing.

---

## Visual Design

**Theme:** D&D / dark fantasy  
**Fonts:** Cinzel Decorative (headings, brand), Cinzel (labels, nav, UI text), EB Garamond (body, italic flavour text)  
**Palette:**

| Token | Value | Usage |
|---|---|---|
| Background | `#0e0b07` | Page background |
| Surface | `#1a1308` / `#120e07` | Cards, panels |
| Border | `#4a3820` | Card borders |
| Gold | `#c9a227` | Headings, accents, active states |
| Body text | `#d4b483` | General text |
| Muted | `#7a6030` | Secondary text, subtitles |

**Arcade button gem colours:**

| Button | Colour | Glow |
|---|---|---|
| Music | Sapphire blue | `rgba(80,120,255,0.7)` |
| Ambiance | Emerald green | `rgba(40,200,100,0.7)` |
| Effects | Ruby red | `rgba(220,50,50,0.7)` |
| Sound slot (empty) | Dark stone | none |
| Sound slot (filled) | Amethyst purple | `rgba(80,40,160,0.4)` |
| Sound slot (selected) | Bright amethyst | `rgba(160,80,255,0.7)` |

**Buttons** are circular CSS domes with:
- Radial gradient fill simulating depth
- Brushed-metal bezel (`::before` pseudo-element)
- Specular highlight (`::after` pseudo-element)
- Drop shadow for 3D lift (`box-shadow` with vertical offset)
- `translateY(3px)` press animation on `:active`
- Coloured glow `box-shadow` on active/selected state

**Responsive:** CSS Grid `repeat(3, 1fr)` for the button grid. Font sizes use `clamp()`. Panel expands to full width on mobile. Minimum tap target 44 px.

---

## Pages

### 1. Instructions (`instructions.html`) — "The Lore"

Nav: `Lore | Board | Wayfinding`

Three section cards, each with icon, Cinzel title, numbered steps, and an optional gold-bordered callout:

1. **Using the Soundboard** — explains the two-step press (group → slot), includes a mini button illustration showing the 3+6 layout, callout notes that Music runes support playlists.
2. **Connecting Bluetooth** — hold BT button 2 s, chime confirms, device remembers speaker.
3. **Connecting to WiFi** — hotspot fallback (`SoundMachine-Setup` / `soundmachine1`), navigate to provisioning page, connect & reboot.

### 2. Board (`index.html`)

Nav: `Lore | Board | Wayfinding`

**Layout (top to bottom):**

1. Page heading + subtitle
2. Instruction hint: *"① Select Group → ② Tap Slot"*
3. **Cabinet panel** — dark stone surface with corner ornaments, contains the 3×3 button grid
4. **Config panel** — slides in below the cabinet when a slot is selected; hidden by default
5. Restart button — *"⟳ Awaken the Machine"*

**Button grid (3×3):**

- Row 1: Music, Ambiance, Effects group buttons
- Rows 2–3: Sound slots I–VI with editable labels

**Interaction flow:**

1. User taps a **group button** → it highlights (gem glow); previously active group deselects.
2. User taps a **sound slot** → config panel slides in below the grid.
3. Panel heading shows slot number + active group (e.g. *"Rune I — Music"*).
4. Tapping a different slot updates the panel in place. Tapping the active slot or pressing Cancel closes the panel.
5. Tapping a group button while a slot is selected updates the panel to show that group's config for the same slot (no need to re-select the slot).

**Config panel — Music group:**

- Text input: Button Label (shared across all groups for this slot)
- Playlist section: ordered list of track filenames, each row has the filename and a remove (✕) button (reordering is done by removing and re-adding tracks)
- *"✦ Add track from library"* button → opens a dropdown/select populated from `GET /api/sounds/library/music`; selecting a file appends it to the list
- *"Inscribe"* (save) / *"Cancel"* buttons
- On save: `PUT /api/config/label/<index>` then `PUT /api/sounds/music/<index>` with the ordered playlist array

**Config panel — Ambiance / Effects groups:**

- Text input: Button Label (same field, shared)
- Single file select: dropdown populated from `GET /api/sounds/library/<group>`; shows current selection
- *"Inscribe"* / *"Cancel"* buttons
- On save: `PUT /api/config/label/<index>` then `PUT /api/sounds/<group>/<index>`

**Upload:**

Each library dropdown includes an *"Upload new file…"* option at the top. Selecting it triggers a hidden `<input type="file">` → `POST /api/upload/<group>` → on success, refreshes the library dropdown and selects the new file automatically.

**Slot button display:**

- Empty slots: dark stone dome, label reads *"dormant"* in near-invisible colour
- Filled slots: amethyst dome, shows editable label + track count / filename
- Selected slot: bright amethyst with glow

### 3. WiFi Setup (`wifi.html`) — "Wayfinding"

Apply shared nav and `styles.css`. All existing JS logic and API calls remain unchanged. Restyled to match the D&D theme (section card, Cinzel headings, gold accents).

---

## API Changes

### `GET /api/config` (existing — extended)

The existing endpoint must be updated to include `button_labels` in its response and to return music slots in the new array-of-arrays format. `board.js` loads this once on page load and treats it as the source of truth for all slot state.

---

## New API Endpoints

### `PUT /api/config/label/<int:index>`

Updates a single button label.

**Request body:** `{ "label": "Battle Theme" }`  
**Validation:** `index` 0–5; label is a non-empty string (max 32 chars).  
**Response:** `{ "status": "ok" }`  
**Side effect:** Writes updated `config.json` to disk.

### `PUT /api/sounds/music/<int:index>`

Replaces the playlist array for a music slot.

**Request body:** `{ "paths": ["sounds/music/a.ogg", "sounds/music/b.ogg"] }` or `{ "paths": null }` to clear.  
**Validation:** `index` 0–5; each path must exist in `sounds/music/` and have a valid audio extension.  
**Response:** `{ "status": "ok" }`

### `GET /api/sounds/library/<group>`

Returns the list of uploaded audio files available for a group.

**Response:** `{ "files": ["sounds/music/Spikeroog.ogg", ...] }` — filenames only, sorted alphabetically.  
**Validation:** `group` must be one of `music`, `ambiance`, `effects`.

---

## Audio Player: Sequential Playlist

### `audio_player.py`

New method replaces `play_music(path)`:

```python
def play_music_playlist(self, paths: list[str]) -> None
```

- Stores `paths` as `self._playlist` and resets `self._playlist_index = 0`.
- Loads and plays the first track via `pygame.mixer.music`.
- Calls `pygame.mixer.music.set_endevent(MUSIC_END_EVENT)` so the event loop is notified when the track finishes.

New method called by the event loop:

```python
def advance_playlist(self) -> None
```

- Increments `_playlist_index` (wraps to 0 after last track).
- Fades out current track (200 ms), then plays next.

`play_music_playlist(["single.ogg"])` behaves identically to the old `play_music("single.ogg")` — the track loops via the end-event advancing back to index 0.

`stop_music()` clears `_playlist` and `_playlist_index` in addition to its existing fadeout.

### `main.py`

- Registers `MUSIC_END_EVENT` with pygame.
- In the main event loop, polls `for event in pygame.event.get()` and calls `audio_player.advance_playlist()` on `MUSIC_END_EVENT`.
- Passes playlist arrays (not single strings) to `button_handler`.

### `button_handler.py`

- Calls `audio_player.play_music_playlist(paths)` instead of `audio_player.play_music(path)`.
- The toggle-off path calls `audio_player.stop_music()` unchanged.

---

## Shared Frontend Assets

### `styles.css`

Contains all D&D theme tokens, nav styles, arcade button styles (dome, bezel, glow states), section card styles, panel styles, and responsive breakpoints. Imported by all three HTML pages.

### `utils.js`

```js
async function apiFetch(url, options = {})  // wraps fetch, shows toast on error
function showToast(message, type = 'info')  // 'info' | 'success' | 'error'
```

Toast is a small fixed notification (bottom-right) styled in the D&D theme. Auto-dismisses after 3 s.

### `board.js`

State:
- `activeGroup` — `'music' | 'ambiance' | 'effects' | null`
- `activeSlot` — `0–5 | null`
- `config` — local copy of the full config object fetched from `GET /api/config`
- `library` — cached file list per group

Key functions:
- `selectGroup(group)` — updates `activeGroup`, re-renders group button states, updates panel if a slot is open
- `selectSlot(index)` — updates `activeSlot`, renders panel for `(activeGroup, index)`
- `renderPanel()` — builds Music or Ambiance/Effects panel DOM based on `activeGroup`
- `saveSlot()` — calls label + sound endpoints, updates local `config`, refreshes slot button display
- `loadLibrary(group)` — fetches `GET /api/sounds/library/<group>`, caches result, populates dropdowns

---

## Out of Scope

- Drag-to-reorder tracks in the playlist (tracks can be removed and re-added in order; true drag-and-drop is deferred)
- Real-time playback status in the web UI
- Multiple simultaneous ambiance or effects tracks
- Any changes to the GPIO button layout or hardware wiring
