import pytest
from state_machine import StateMachine, Group

def test_initial_state_is_idle():
    sm = StateMachine()
    assert sm.active_group is None
    assert sm.state == "IDLE"

def test_pressing_group_button_sets_group():
    sm = StateMachine()
    sm.select_group(0)
    assert sm.active_group == Group.MUSIC
    assert sm.state == "GROUP_SELECTED"

def test_pressing_same_group_keeps_active():
    sm = StateMachine()
    sm.select_group(0)
    sm.select_group(0)
    assert sm.active_group == Group.MUSIC
    assert sm.state == "GROUP_SELECTED"

def test_pressing_different_group_switches():
    sm = StateMachine()
    sm.select_group(0)
    sm.select_group(1)
    assert sm.active_group == Group.AMBIANCE

def test_select_sound_returns_group_and_index_when_active():
    sm = StateMachine()
    sm.select_group(0)
    result = sm.select_sound(3)
    assert result == (Group.MUSIC, 3)

def test_select_sound_returns_none_when_no_group():
    sm = StateMachine()
    result = sm.select_sound(0)
    assert result is None

def test_effects_group():
    sm = StateMachine()
    sm.select_group(2)
    assert sm.active_group == Group.EFFECTS
