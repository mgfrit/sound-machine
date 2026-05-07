from enum import Enum

# The three sound categories the machine supports.
# Integer values (0, 1, 2) match the physical order of the group buttons on the device.
class Group(Enum):
    MUSIC = 0    # Looping background music — supports multi-track playlists
    AMBIANCE = 1 # Looping ambient atmosphere — rain, fire, tavern, etc.
    EFFECTS = 2  # One-shot sound effects — sword strike, door creak, etc.


# Tracks which group button was last pressed so rune presses know what to do.
#
# The physical device uses a two-step interaction:
#   Step 1 — Press a group button (Music / Ambiance / Effects)
#   Step 2 — Press a rune button (I–VI) to play/stop that slot's sound
#
# This class sits between those two steps: it remembers which group is active
# so ButtonHandler can look up the right sound when a rune is pressed.
class StateMachine:
    def __init__(self):
        self.active_group = None  # Most recently selected Group, or None if no group pressed yet
        self.state = "IDLE"       # Human-readable label (informational only, not used for logic)

    def select_group(self, index):
        """Record which group button was pressed. Called by ButtonHandler on every group press."""
        group = Group(index)
        self.active_group = group
        self.state = "GROUP_SELECTED"

    def select_sound(self, index):
        """Called when a rune button is pressed.
        Returns (active_group, slot_index) so ButtonHandler knows what to play,
        or None if no group has been selected yet (the rune press is ignored)."""
        if self.active_group is None:
            return None
        return (self.active_group, index)
