"""Main window menu bar builder."""

import wx

from utils.i18n import _


def create_menu_bar(owner):
    """Create and bind the main window menu bar."""
    menu_bar = wx.MenuBar()

    menu_bar.Append(_create_file_menu(owner), _("&File"))
    menu_bar.Append(_create_deck_menu(owner), _("&Deck"))
    menu_bar.Append(_create_playback_menu(owner), _("&Playback"))
    menu_bar.Append(_create_view_menu(owner), _("&View"))
    menu_bar.Append(_create_tools_menu(owner), _("&Tools"))
    menu_bar.Append(_create_help_menu(owner), _("&Help"))

    _bind_menu_events(owner)
    return menu_bar


def _create_file_menu(owner):
    """Create the File menu."""
    file_menu = wx.Menu()
    file_menu.Append(wx.ID_NEW, _("&New Project") + "...\tCtrl+N")
    file_menu.Append(wx.ID_OPEN, _("&Open Project") + "...\tCtrl+O")
    file_menu.Append(wx.ID_SAVE, _("&Save Project") + "\tCtrl+S")
    file_menu.Append(wx.ID_SAVEAS, _("Save Project &As") + "...\tCtrl+Shift+S")
    file_menu.AppendSeparator()

    owner.import_m3u_item = file_menu.Append(wx.ID_ANY, _("&Import M3U Playlist") + "...\tCtrl+I")
    owner.export_m3u_item = file_menu.Append(wx.ID_ANY, _("&Export M3U Playlist") + "...\tCtrl+E")

    file_menu.AppendSeparator()
    owner.recent_menu = wx.Menu()
    file_menu.AppendSubMenu(owner.recent_menu, _("&Recent Files"))
    owner._update_recent_files_menu()

    file_menu.AppendSeparator()
    file_menu.Append(wx.ID_EXIT, _("E&xit") + "\tAlt+F4")
    return file_menu


def _create_deck_menu(owner):
    """Create the Deck menu."""
    owner.deck_menu = wx.Menu()
    owner.load_file_item = owner.deck_menu.Append(wx.ID_ANY, _("Load File") + "...\tCtrl+F")
    owner.load_url_item = owner.deck_menu.Append(wx.ID_ANY, _("Load URL") + "...\tCtrl+U")
    owner.load_input_item = owner.deck_menu.Append(wx.ID_ANY, _("Load sound card input") + "...\tCtrl+D")
    owner.deck_menu.AppendSeparator()
    owner.set_intro_item = owner.deck_menu.Append(wx.ID_ANY, _("Set Intro File") + "...")
    owner.clear_intro_item = owner.deck_menu.Append(wx.ID_ANY, _("Clear Intro File"))
    owner.deck_output_device_menu = owner._create_deck_output_device_menu(store_attr='deck_output_device_items')
    owner.deck_menu.AppendSubMenu(owner.deck_output_device_menu, _("Output Device"))
    owner.deck_menu.AppendSeparator()
    owner.rename_item = owner.deck_menu.Append(wx.ID_ANY, _("Rename Deck") + "...\tF2")
    owner.unload_item = owner.deck_menu.Append(wx.ID_ANY, _("Unload Deck") + "\tDel")
    owner.record_deck_menu_item = owner.deck_menu.Append(wx.ID_ANY, _("Start Recording Deck") + "\tCtrl+Shift+R")
    owner.unload_item.Enable(False)
    owner.record_deck_menu_item.Enable(False)
    return owner.deck_menu


def _create_playback_menu(owner):
    """Create the Playback menu."""
    playback_menu = wx.Menu()
    owner.play_all_item = playback_menu.Append(wx.ID_ANY, _("Play/Pause all decks") + "\tCtrl+P")
    owner.stop_all_item = playback_menu.Append(wx.ID_ANY, _("Stop all decks") + "\tCtrl+.")
    playback_menu.AppendSeparator()
    owner.play_active_item = playback_menu.Append(wx.ID_ANY, _("Play active deck") + "\tCtrl+Shift+P")
    owner.stop_active_item = playback_menu.Append(wx.ID_ANY, _("Stop active deck") + "\tCtrl+Shift+.")
    owner.toggle_loop_item = playback_menu.Append(wx.ID_ANY, _("Toggle Loop") + "\tCtrl+L")
    owner.toggle_mute_item = playback_menu.Append(wx.ID_ANY, _("Toggle Mute") + "\tCtrl+M")
    owner.jump_to_item = playback_menu.Append(wx.ID_ANY, _("Jump to time") + "\tCtrl+J")
    return playback_menu


def _create_view_menu(owner):
    """Create the View menu."""
    view_menu = wx.Menu()
    owner.statusbar_item = view_menu.AppendCheckItem(wx.ID_ANY, _("&Status Bar") + "\tCtrl+T")
    owner.statusbar_item.Check(True)
    owner.level_meter_item = view_menu.AppendCheckItem(wx.ID_ANY, _("&Level Meter"))
    owner.level_meter_item.Check(owner.config_manager.getboolean('UI', 'show_level_meter', True))
    view_menu.AppendSeparator()
    owner.theme_item = view_menu.Append(wx.ID_ANY, _("Toggle &Theme") + "\tCtrl+Shift+T")
    return view_menu


def _create_tools_menu(owner):
    """Create the Tools menu."""
    tools_menu = wx.Menu()
    owner.record_menu_item = tools_menu.Append(wx.ID_ANY, _("Start &Recording") + "\tCtrl+R")
    owner.stream_menu_item = tools_menu.Append(wx.ID_ANY, _("Start &Livestream") + "\tF8")
    tools_menu.AppendSeparator()
    owner.effects_menu_item = tools_menu.Append(wx.ID_ANY, _("Audio &Effects") + "...\tCtrl+Shift+E")
    tools_menu.AppendSeparator()
    tools_menu.Append(wx.ID_PREFERENCES, _("&Options") + "...\tCtrl+Shift+O")
    return tools_menu


def _create_help_menu(owner):
    """Create the Help menu."""
    help_menu = wx.Menu()
    help_menu.Append(wx.ID_HELP, _("&Documentation") + "\tF1")
    owner.website_item = help_menu.Append(wx.ID_ANY, _("Open &Website") + "\tCtrl+F1")
    help_menu.AppendSeparator()
    help_menu.Append(wx.ID_ABOUT, _("&About") + "...")
    return help_menu


def _bind_menu_events(owner):
    """Bind all menu events to their handlers."""
    owner.Bind(wx.EVT_MENU, owner._on_new_project, id=wx.ID_NEW)
    owner.Bind(wx.EVT_MENU, owner._on_open_project, id=wx.ID_OPEN)
    owner.Bind(wx.EVT_MENU, owner._on_save_project, id=wx.ID_SAVE)
    owner.Bind(wx.EVT_MENU, owner._on_save_project_as, id=wx.ID_SAVEAS)
    owner.Bind(wx.EVT_MENU, owner._on_import_m3u, owner.import_m3u_item)
    owner.Bind(wx.EVT_MENU, owner._on_export_m3u, owner.export_m3u_item)
    owner.Bind(wx.EVT_MENU, owner._on_exit, id=wx.ID_EXIT)
    owner.Bind(wx.EVT_MENU, owner._on_selected_deck_load_file, owner.load_file_item)
    owner.Bind(wx.EVT_MENU, owner._on_selected_deck_load_url, owner.load_url_item)
    owner.Bind(wx.EVT_MENU, owner._on_selected_deck_load_soundcard_input, owner.load_input_item)
    owner.Bind(wx.EVT_MENU, owner._on_selected_deck_set_intro_file, owner.set_intro_item)
    owner.Bind(wx.EVT_MENU, owner._on_selected_deck_clear_intro_file, owner.clear_intro_item)
    owner.Bind(wx.EVT_MENU, lambda e: owner._on_active_rename(), owner.rename_item)
    owner.Bind(wx.EVT_MENU, lambda e: owner._on_active_unload(), owner.unload_item)
    owner.Bind(wx.EVT_MENU, owner._on_selected_deck_toggle_recording, owner.record_deck_menu_item)
    owner.Bind(wx.EVT_MENU, owner._on_global_play_pause, owner.play_all_item)
    owner.Bind(wx.EVT_MENU, owner._on_global_stop, owner.stop_all_item)
    owner.Bind(wx.EVT_MENU, owner._on_active_play_pause, owner.play_active_item)
    owner.Bind(wx.EVT_MENU, owner._on_active_stop, owner.stop_active_item)
    owner.Bind(wx.EVT_MENU, lambda e: owner._on_active_toggle_loop(), owner.toggle_loop_item)
    owner.Bind(wx.EVT_MENU, lambda e: owner._on_active_toggle_mute(), owner.toggle_mute_item)
    owner.Bind(wx.EVT_MENU, owner._on_jump_to_time, owner.jump_to_item)
    owner.Bind(wx.EVT_MENU, owner._on_toggle_statusbar, owner.statusbar_item)
    owner.Bind(wx.EVT_MENU, owner._on_toggle_level_meter, owner.level_meter_item)
    owner.Bind(wx.EVT_MENU, owner._on_toggle_theme, owner.theme_item)
    owner.Bind(wx.EVT_MENU, owner._on_toggle_recording, owner.record_menu_item)
    owner.Bind(wx.EVT_MENU, owner._on_toggle_livestream, owner.stream_menu_item)
    owner.Bind(wx.EVT_MENU, owner._on_show_effects_dialog, owner.effects_menu_item)
    owner.Bind(wx.EVT_MENU, owner._on_options, id=wx.ID_PREFERENCES)
    owner.Bind(wx.EVT_MENU, owner._on_help, id=wx.ID_HELP)
    owner.Bind(wx.EVT_MENU, owner._on_website, owner.website_item)
    owner.Bind(wx.EVT_MENU, owner._on_about, id=wx.ID_ABOUT)
    owner.Bind(wx.EVT_MENU_OPEN, owner._on_menu_open)
