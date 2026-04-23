"""Playlist import/export helpers for the main window."""

import os

import wx

from utils.i18n import _


class M3UPlaylistService:
    """Handle M3U import/export flows for the main window."""

    def __init__(self, owner):
        self.owner = owner

    def import_m3u(self):
        """Import an M3U playlist into free decks."""
        dlg = wx.FileDialog(
            self.owner,
            _("Import M3U Playlist"),
            wildcard="M3U Playlist (*.m3u;*.m3u8)|*.m3u;*.m3u8|" + _("All Files") + " (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        )

        if dlg.ShowModal() == wx.ID_OK:
            m3u_path = dlg.GetPath()
            entries = self.parse_m3u_file(m3u_path)

            if not entries:
                wx.MessageBox(
                    _("No valid entries found in playlist."),
                    _("Import M3U"),
                    wx.OK | wx.ICON_INFORMATION
                )
                dlg.Destroy()
                return

            loaded_count = 0
            skipped_count = 0

            for entry in entries:
                target_deck = self._find_next_free_deck()
                if target_deck is None:
                    skipped_count = len(entries) - loaded_count
                    break

                if target_deck.load_file(entry):
                    if not entry.startswith(('http://', 'https://')):
                        self.owner._preload_deck_audio(target_deck)
                    self.owner._update_deck_panel(target_deck.deck_id)
                    self.owner.config_manager.add_recent_file(entry)
                    loaded_count += 1
                else:
                    skipped_count += 1

            self.owner._update_recent_files_menu()
            if loaded_count > 0:
                self.owner._mark_project_modified()

            if skipped_count > 0:
                message = _("Imported {loaded} entries. {skipped} entries skipped (no free decks or load errors).").format(
                    loaded=loaded_count,
                    skipped=skipped_count,
                )
            else:
                message = _("Imported {loaded} entries.").format(loaded=loaded_count)

            self.owner.SetStatusText(message, 0)

        dlg.Destroy()

    def parse_m3u_file(self, m3u_path):
        """Parse an M3U file and return valid file paths or URLs."""
        entries = []
        m3u_dir = os.path.dirname(os.path.abspath(m3u_path))

        content = None
        for encoding in ['utf-8', 'latin-1']:
            try:
                with open(m3u_path, 'r', encoding=encoding) as file_handle:
                    content = file_handle.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return entries

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith(('http://', 'https://')):
                entries.append(line)
                continue

            if os.path.isabs(line):
                file_path = line
            else:
                file_path = os.path.normpath(os.path.join(m3u_dir, line))

            if os.path.exists(file_path):
                entries.append(file_path)

        return entries

    def export_m3u(self):
        """Export all loaded deck files and URLs to an M3U playlist."""
        entries = [deck.file_path for deck in self.owner.mixer.decks if deck.file_path]

        if not entries:
            wx.MessageBox(
                _("No files loaded in any deck. Nothing to export."),
                _("Export M3U"),
                wx.OK | wx.ICON_INFORMATION
            )
            return

        dlg = wx.FileDialog(
            self.owner,
            _("Export M3U Playlist"),
            wildcard="M3U Playlist (*.m3u)|*.m3u|M3U8 Playlist (*.m3u8)|*.m3u8",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        )

        if dlg.ShowModal() == wx.ID_OK:
            m3u_path = dlg.GetPath()
            if not m3u_path.lower().endswith(('.m3u', '.m3u8')):
                m3u_path += '.m3u'

            try:
                with open(m3u_path, 'w', encoding='utf-8') as file_handle:
                    file_handle.write('#EXTM3U\n')
                    for entry in entries:
                        name = entry if entry.startswith(('http://', 'https://')) else os.path.basename(entry)
                        file_handle.write(f'#EXTINF:-1,{name}\n')
                        file_handle.write(f'{entry}\n')

                self.owner.SetStatusText(
                    _("Exported {count} entries to {file}").format(
                        count=len(entries),
                        file=os.path.basename(m3u_path)
                    ),
                    0
                )

            except IOError as error:
                wx.MessageBox(
                    _("Failed to write playlist file: {}").format(str(error)),
                    _("Error"),
                    wx.OK | wx.ICON_ERROR
                )

        dlg.Destroy()

    def _find_next_free_deck(self):
        """Return the next free deck or None if all decks are occupied."""
        for deck in self.owner.mixer.decks:
            if not deck.file_path:
                return deck
        return None
