from enum import Enum

class Group(Enum):
    MUSIC = 0
    AMBIANCE = 1
    EFFECTS = 2

class StateMachine:
    def __init__(self):
        self.active_group = None
        self.state = "IDLE"

    def select_group(self, index):
        group = Group(index)
        if self.active_group == group:
            self.active_group = None
            self.state = "IDLE"
        else:
            self.active_group = group
            self.state = "GROUP_SELECTED"

    def select_sound(self, index):
        if self.active_group is None:
            return None
        return (self.active_group, index)
