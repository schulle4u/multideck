"""
Keyboard shortcut definitions for the main window
"""

import wx
from config.defaults import (
    MODE_MIXER, MODE_SOLO, MODE_AUTOMATIC, MODE_MULTIROOM
)


def setup_keyboard_shortcuts(owner):
    """Setup keyboard accelerators"""
    accel_entries = []

    # Ctrl+1 to Ctrl+0 for deck selection, Ctrl + Alt if more than 10 decks
    num_decks = owner.config_manager.get_deck_count()
    for i in range(1, num_decks + 1):
        digit = i % 10
        key = ord(str(digit)) if digit != 0 else ord('0')
        if i <= 10:
            modifiers = wx.ACCEL_CTRL
        else:
            modifiers = wx.ACCEL_CTRL | wx.ACCEL_ALT
        owner._add_keyboard_shortcut(
            accel_entries,
            modifiers,
            key,
            lambda e, deck_idx=i-1: owner._on_deck_shortcut(deck_idx)
        )

    # Ctrl+Tab / Ctrl+Shift+Tab for next/previous deck
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL, wx.WXK_TAB, owner._on_next_deck)
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_TAB, owner._on_previous_deck)

    # F3-F7 for mode selection
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_NORMAL, wx.WXK_F3, lambda e: owner._set_mode_with_ui(MODE_MIXER))
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_NORMAL, wx.WXK_F4, lambda e: owner._set_mode_with_ui(MODE_SOLO))
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_NORMAL, wx.WXK_F5, lambda e: owner._set_mode_with_ui(MODE_AUTOMATIC))
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_NORMAL, wx.WXK_F7, lambda e: owner._set_mode_with_ui(MODE_MULTIROOM))

    # Ctrl+M for mute active deck
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL, ord('M'), owner._on_mute_active_deck)

    # Ctrl+L for loop active deck
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL, ord('L'), owner._on_loop_active_deck)

    # Ctrl+R for recorder toggle
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL, ord('R'), owner._on_toggle_recording)

    # Ctrl+Shift+R for per-deck recording toggle
    owner._add_keyboard_shortcut(
        accel_entries,
        wx.ACCEL_CTRL | wx.ACCEL_SHIFT,
        ord('R'),
        owner._on_toggle_deck_recording_shortcut
    )

    # F6 for jump to deck list (accessibility standard)
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_NORMAL, wx.WXK_F6, owner._on_jump_to_deck_list)

    # Ctrl+F for load file
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL, ord('F'), owner._on_shortcut_load_file)

    # Ctrl+U for load URL
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL, ord('U'), owner._on_shortcut_load_url)

    # Ctrl+D for load soundcard input
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL, ord('D'), owner._on_shortcut_load_soundcard_input)

    # F2 for rename deck
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_NORMAL, wx.WXK_F2, owner._on_shortcut_rename)

    # Delete for unload deck
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_NORMAL, wx.WXK_DELETE, owner._on_shortcut_unload)

    # Ctrl+Up/Down for deck volume
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL, wx.WXK_UP, lambda e: owner._on_deck_volume_change(5))
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL, wx.WXK_DOWN, lambda e: owner._on_deck_volume_change(-5))

    # Ctrl+Left/Right for deck balance
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL, wx.WXK_LEFT, lambda e: owner._on_deck_balance_change(-5))
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL, wx.WXK_RIGHT, lambda e: owner._on_deck_balance_change(5))

    # Ctrl+Shift+Up/Down for master volume
    owner._add_keyboard_shortcut(
        accel_entries,
        wx.ACCEL_CTRL | wx.ACCEL_SHIFT,
        wx.WXK_UP,
        lambda e: owner._on_master_volume_shortcut(5)
    )
    owner._add_keyboard_shortcut(
        accel_entries,
        wx.ACCEL_CTRL | wx.ACCEL_SHIFT,
        wx.WXK_DOWN,
        lambda e: owner._on_master_volume_shortcut(-5)
    )

    # Alt+Left/Right for seek ±5 seconds
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_ALT, wx.WXK_RIGHT, owner._on_seek_forward)
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_ALT, wx.WXK_LEFT, owner._on_seek_backward)

    # Alt+Shift+Left/Right for seek ±30 seconds
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_ALT | wx.ACCEL_SHIFT, wx.WXK_RIGHT, owner._on_seek_forward_large)
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_ALT | wx.ACCEL_SHIFT, wx.WXK_LEFT, owner._on_seek_backward_large)

    # Ctrl+J for jump to time
    owner._add_keyboard_shortcut(accel_entries, wx.ACCEL_CTRL, ord('J'), owner._on_jump_to_time)

    # Set accelerator table
    accel_table = wx.AcceleratorTable(accel_entries)
    owner.SetAcceleratorTable(accel_table)
