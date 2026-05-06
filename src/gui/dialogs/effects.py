"""
Effects dialog
"""
import wx
import os
import sys
from gui.dialogs.accessibility import _ValueDisplayAccessible, _FormattedSliderAccessible
from utils.i18n import _


class EffectsDialog(wx.Dialog):
    """Modeless dialog for real-time audio effect controls."""

    def __init__(self, parent, mixer):
        """
        Initialize effects dialog.

        Args:
            parent: Parent window (MainFrame)
            mixer: Mixer instance with master_effects and per-deck effect chains
        """
        super().__init__(parent, title=_("Audio Effects"),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.mixer = mixer
        self.main_frame = parent

        self._create_ui()
        self._fit_to_pages()
        self.SetMinSize(self.GetSize())
        self.Center()

        # Apply theme
        if hasattr(parent, 'theme_manager') and parent.theme_manager:
            parent.theme_manager.apply_theme(self)

        if sys.platform != 'win32':
            self.Bind(wx.EVT_SHOW, self._on_first_show)

        # Focus category list on dialog open
        self.category_list.SetFocus()

        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def _on_first_show(self, event):
        """Pre-size hidden pages after realization to avoid layout warnings on Linux."""
        event.Skip()
        if not event.IsShown():
            return
        self.Unbind(wx.EVT_SHOW)
        sz = self.page_container.GetClientSize()
        if sz.width > 0 and sz.height > 0:
            for page in self.pages:
                if not page.IsShown():
                    page.SetSize(0, 0, sz.width, sz.height)
                    page.Layout()

    def _on_char_hook(self, event):
        """Close dialog on Escape key."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Close()
        else:
            event.Skip()

    def _on_close(self, event):
        """Handle dialog close - clear reference in main frame."""
        if hasattr(self.main_frame, '_effects_dialog'):
            self.main_frame._effects_dialog = None
        self.Destroy()

    def _on_page_changed(self, event):
        """Handle category selection change - switch page."""
        event.Skip()
        self._show_page(self.category_list.GetSelection())

    def _show_page(self, idx):
        """Show page at idx, hide all others."""
        target = self.pages[idx]
        for i, page in enumerate(self.pages):
            page.Show(i == idx)
        self.page_container.Layout()
        target.Layout()

    def _fit_to_pages(self):
        """Fit the dialog to its initial content with minimum size constraints."""
        self.Fit()
        size = self.GetSize()
        self.SetSize(max(size.width, 700), max(size.height, 600))

    def _create_ui(self):
        """Create the dialog UI with ListBox + page container."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        book_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Build page names list: interleaved built-in + VST entries per chain
        page_names = [
            _("Master: Built-in Effects"),
            _("Master: VST Plugins"),
        ]
        for deck in self.mixer.decks:
            if deck.effects:
                page_names.append(f"{deck.name}: {_('Built-in Effects')}")
                page_names.append(f"{deck.name}: {_('VST Plugins')}")

        list_sizer = wx.BoxSizer(wx.VERTICAL)
        list_label = wx.StaticText(panel, label=_("&Effect Chains"))
        list_sizer.Add(list_label, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 5)
        self.category_list = wx.ListBox(panel, choices=page_names)
        self.category_list.SetName(_("Effect Chains"))
        self.category_list.SetLabel(_("Effect Chains"))
        self.category_list.SetSelection(0)
        list_sizer.Add(self.category_list, 1, wx.EXPAND | wx.ALL, 5)
        book_sizer.Add(list_sizer, 0, wx.EXPAND)

        self.page_container = wx.Panel(panel)
        self.page_sizer = wx.BoxSizer(wx.VERTICAL)
        self.pages = []

        # Master built-in effects page
        master_panel = self._create_effect_panel(
            self.page_container, self.mixer.master_effects, _("Master"))
        self.page_sizer.Add(master_panel, 1, wx.EXPAND)
        self.pages.append(master_panel)

        # Master VST page
        master_vst = self._create_vst_panel(
            self.page_container, self.mixer.master_effects, _("Master"))
        master_vst.Show(False)
        self.page_sizer.Add(master_vst, 1, wx.EXPAND)
        self.pages.append(master_vst)

        # Per-deck pages (hidden at creation to avoid GTK allocating 0 size)
        for deck in self.mixer.decks:
            if deck.effects:
                deck_panel = self._create_effect_panel(
                    self.page_container, deck.effects, deck.name)
                deck_panel.Show(False)
                self.page_sizer.Add(deck_panel, 1, wx.EXPAND)
                self.pages.append(deck_panel)

                deck_vst = self._create_vst_panel(
                    self.page_container, deck.effects, deck.name)
                deck_vst.Show(False)
                self.page_sizer.Add(deck_vst, 1, wx.EXPAND)
                self.pages.append(deck_vst)

        self.page_container.SetSizer(self.page_sizer)

        book_sizer.Add(self.page_container, 1, wx.EXPAND | wx.ALL, 5)

        self.category_list.Bind(wx.EVT_LISTBOX, self._on_page_changed)

        main_sizer.Add(book_sizer, 1, wx.EXPAND | wx.ALL, 5)

        # Close button
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()
        close_btn = wx.Button(panel, wx.ID_CLOSE, _("&Close"))
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        button_sizer.Add(close_btn, 0, wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.BOTTOM | wx.RIGHT, 5)

        panel.SetSizer(main_sizer)

    def _create_effect_panel(self, parent, effect_chain, chain_name):
        """Create a scrolled panel with all effect controls for one chain."""
        panel = wx.ScrolledWindow(parent)
        panel.SetScrollRate(0, 10)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Global enable
        enable_cb = wx.CheckBox(panel, label=_("Enable effects for {}").format(chain_name))
        enable_cb.SetValue(effect_chain.enabled)
        enable_cb.Bind(wx.EVT_CHECKBOX,
                       lambda e: self._set_chain_enabled(effect_chain, e.IsChecked()))
        sizer.Add(enable_cb, 0, wx.ALL, 10)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Reverb
        sizer.Add(self._create_reverb_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        # Delay
        sizer.Add(self._create_delay_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        # EQ
        sizer.Add(self._create_eq_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        # Chorus
        sizer.Add(self._create_chorus_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        # Compressor
        sizer.Add(self._create_compressor_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        # Limiter
        sizer.Add(self._create_limiter_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        # Gain
        sizer.Add(self._create_gain_section(panel, effect_chain, chain_name),
                  0, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(sizer)
        panel.FitInside()
        return panel

    def _set_chain_enabled(self, effect_chain, enabled):
        effect_chain.enabled = enabled

    # ------------------------------------------------------------------ #
    #  VST plugin panel                                                    #
    # ------------------------------------------------------------------ #

    def _create_vst_panel(self, parent, effect_chain, chain_name):
        """Create a panel that manages VST plugins for one effect chain."""
        panel = wx.Panel(parent)
        outer = wx.BoxSizer(wx.VERTICAL)

        # ---- Section 1: plugin management (StaticBoxSizer) ----
        # All child widgets are parented to mgmt_sb (the StaticBox), not to
        # mgmt_panel.  This matches the built-in effect sections and ensures
        # Orca reads them correctly via the AT-SPI accessible name of the box.
        mgmt_panel = wx.Panel(panel)
        mgmt_sizer = wx.BoxSizer(wx.VERTICAL)
        mgmt_box = wx.StaticBoxSizer(wx.VERTICAL, mgmt_panel, _("VST Plugins"))
        mgmt_sb = mgmt_box.GetStaticBox()

        vst_lb = wx.ListBox(mgmt_sb, style=wx.LB_SINGLE)
        vst_lb.SetName(f"{chain_name}: {_('VST Plugins')}")
        vst_lb.SetMinSize((-1, 80))
        mgmt_box.Add(vst_lb, 0, wx.EXPAND | wx.ALL, 5)

        enable_cb = wx.CheckBox(mgmt_sb, label=_("Enable selected plugin"))
        enable_cb.SetName(f"{chain_name}: {_('Enable selected VST plugin')}")
        enable_cb.Enable(False)
        mgmt_box.Add(enable_cb, 0, wx.LEFT | wx.BOTTOM, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_btn = wx.Button(mgmt_sb, label=_("&Add VST File") + "...")
        add_bundle_btn = wx.Button(mgmt_sb, label=_("Add VST &Bundle") + "...")
        remove_btn = wx.Button(mgmt_sb, label=_("&Remove"))
        up_btn = wx.Button(mgmt_sb, label=_("Move &Up"))
        down_btn = wx.Button(mgmt_sb, label=_("Move &Down"))
        editor_btn = wx.Button(mgmt_sb, label=_("Open &Editor"))
        for b in (add_btn, add_bundle_btn, remove_btn, up_btn, down_btn, editor_btn):
            btn_sizer.Add(b, 0, wx.RIGHT, 5)
        mgmt_box.Add(btn_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        load_status = wx.StaticText(mgmt_sb, label="")
        load_status.Show(False)
        mgmt_box.Add(load_status, 0, wx.LEFT | wx.BOTTOM, 5)

        mgmt_sizer.Add(mgmt_box, 1, wx.EXPAND)
        mgmt_panel.SetSizer(mgmt_sizer)
        outer.Add(mgmt_panel, 0, wx.EXPAND | wx.ALL, 5)

        # ---- Section 2: parameter panel (StaticBoxSizer) ----
        param_panel = wx.Panel(panel)
        param_sizer = wx.BoxSizer(wx.VERTICAL)
        param_box = wx.StaticBoxSizer(
            wx.VERTICAL, param_panel, _("Parameters of selected plugin"))
        param_sb = param_box.GetStaticBox()

        param_scroll = wx.ScrolledWindow(param_sb)
        param_scroll.SetScrollRate(0, 10)
        param_inner = wx.BoxSizer(wx.VERTICAL)
        param_scroll.SetSizer(param_inner)
        param_box.Add(param_scroll, 1, wx.EXPAND | wx.ALL, 5)

        param_sizer.Add(param_box, 1, wx.EXPAND)
        param_panel.SetSizer(param_sizer)
        outer.Add(param_panel, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(outer)

        # Collect mutable state in a dict so closures can mutate it
        state = {
            'listbox': vst_lb,
            'enable_cb': enable_cb,
            'add_btn': add_btn,
            'add_bundle_btn': add_bundle_btn,
            'remove_btn': remove_btn,
            'up_btn': up_btn,
            'down_btn': down_btn,
            'editor_btn': editor_btn,
            'load_status': load_status,
            'mgmt_panel': mgmt_panel,
            'param_scroll': param_scroll,
            'param_inner': param_inner,
        }

        self._refresh_vst_list(state, effect_chain)
        self._update_vst_buttons(state, effect_chain)

        # ---- Event bindings ----

        def on_select(event):
            event.Skip()
            self._on_vst_selected(state, effect_chain, chain_name)

        def on_enable(event):
            idx = vst_lb.GetSelection()
            if idx != wx.NOT_FOUND:
                effect_chain.enable_vst(idx, event.IsChecked())
                self._refresh_vst_list(state, effect_chain)
                vst_lb.SetSelection(idx)

        def on_add(event):
            self._on_vst_add_file(state, effect_chain, chain_name)

        def on_add_bundle(event):
            self._on_vst_add_bundle(state, effect_chain, chain_name)

        def on_remove(event):
            self._on_vst_remove(state, effect_chain, chain_name)

        def on_up(event):
            idx = vst_lb.GetSelection()
            if idx != wx.NOT_FOUND and idx > 0:
                effect_chain.move_vst(idx, -1)
                self._refresh_vst_list(state, effect_chain)
                vst_lb.SetSelection(idx - 1)
                self._on_vst_selected(state, effect_chain, chain_name)

        def on_down(event):
            idx = vst_lb.GetSelection()
            if idx != wx.NOT_FOUND and idx < len(effect_chain.vst_slots) - 1:
                effect_chain.move_vst(idx, 1)
                self._refresh_vst_list(state, effect_chain)
                vst_lb.SetSelection(idx + 1)
                self._on_vst_selected(state, effect_chain, chain_name)

        def on_editor(event):
            idx = vst_lb.GetSelection()
            if idx == wx.NOT_FOUND:
                return
            slot = effect_chain.vst_slots[idx]
            plugin = slot['plugin']
            try:
                plugin.show_editor()
            except AttributeError:
                wx.MessageBox(
                    _("The pedalboard library does not support opening native plugin "
                      "editors in this version.\n\nUse the parameter panel below to "
                      "control the plugin."),
                    _("Native Editor Not Available"),
                    wx.OK | wx.ICON_INFORMATION,
                )
            except Exception as e:
                wx.MessageBox(str(e), _("Editor Error"), wx.OK | wx.ICON_ERROR)

        vst_lb.Bind(wx.EVT_LISTBOX, on_select)
        enable_cb.Bind(wx.EVT_CHECKBOX, on_enable)
        add_btn.Bind(wx.EVT_BUTTON, on_add)
        add_bundle_btn.Bind(wx.EVT_BUTTON, on_add_bundle)
        remove_btn.Bind(wx.EVT_BUTTON, on_remove)
        up_btn.Bind(wx.EVT_BUTTON, on_up)
        down_btn.Bind(wx.EVT_BUTTON, on_down)
        editor_btn.Bind(wx.EVT_BUTTON, on_editor)

        return panel

    # ---- VST list helpers ----

    @staticmethod
    def _refresh_vst_list(state, effect_chain):
        """Rebuild the VST ListBox from current vst_slots."""
        lb = state['listbox']
        sel = lb.GetSelection()
        lb.Clear()
        for slot in effect_chain.vst_slots:
            prefix = "[+] " if slot['enabled'] else "[ ] "
            lb.Append(prefix + slot['name'])
        if sel != wx.NOT_FOUND and sel < lb.GetCount():
            lb.SetSelection(sel)

    @staticmethod
    def _update_vst_buttons(state, effect_chain):
        idx = state['listbox'].GetSelection()
        has_sel = idx != wx.NOT_FOUND
        count = len(effect_chain.vst_slots)
        state['remove_btn'].Enable(has_sel)
        state['up_btn'].Enable(has_sel and idx > 0)
        state['down_btn'].Enable(has_sel and idx < count - 1)
        state['editor_btn'].Enable(has_sel)
        state['enable_cb'].Enable(has_sel)
        if has_sel:
            state['enable_cb'].SetValue(effect_chain.vst_slots[idx]['enabled'])

    def _on_vst_selected(self, state, effect_chain, chain_name):
        self._update_vst_buttons(state, effect_chain)
        idx = state['listbox'].GetSelection()
        if idx == wx.NOT_FOUND:
            return
        slot = effect_chain.vst_slots[idx]
        self._rebuild_vst_param_panel(
            state['param_scroll'], state['param_inner'],
            effect_chain, idx, chain_name, slot['name'])

    def _on_vst_add_file(self, state, effect_chain, chain_name):
        wildcard = (
            "VST3 Plugin Files (*.vst3)|*.vst3"
            "|AU Plugin Files (*.component)|*.component"
            "|All Files (*.*)|*.*"
        )
        dlg = wx.FileDialog(
            self, _("Load VST Plugin File"),
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        path = dlg.GetPath()
        dlg.Destroy()
        self._load_vst_path(state, effect_chain, chain_name, path)

    def _on_vst_add_bundle(self, state, effect_chain, chain_name):
        dlg = wx.DirDialog(
            self,
            _("Load VST Plugin Bundle"),
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        path = dlg.GetPath()
        dlg.Destroy()
        self._load_vst_path(state, effect_chain, chain_name, path)

    def _choose_vst_plugin_name(self, effect_chain, path):
        plugin_names = effect_chain.get_plugin_names(path)
        if len(plugin_names) <= 1:
            return plugin_names[0] if plugin_names else None

        dlg = wx.SingleChoiceDialog(
            self,
            _("This VST3 bundle contains multiple plugins. Select the one to load."),
            _("Select VST Plugin"),
            plugin_names,
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return False
        plugin_name = dlg.GetStringSelection()
        dlg.Destroy()
        return plugin_name

    def _load_vst_path(self, state, effect_chain, chain_name, path):
        plugin_name = self._choose_vst_plugin_name(effect_chain, path)
        if plugin_name is False:
            return

        plugin_filename = plugin_name or os.path.basename(path.rstrip(os.sep))
        state['load_status'].SetLabel(_("Loading {}...").format(plugin_filename))
        state['load_status'].Show(True)
        state['mgmt_panel'].Layout()
        state['add_btn'].Disable()
        state['add_bundle_btn'].Disable()
        wx.BeginBusyCursor()
        wx.SafeYield(None, True)

        try:
            error = effect_chain.add_vst(path, plugin_name=plugin_name)
        finally:
            wx.EndBusyCursor()
            state['load_status'].SetLabel("")
            state['load_status'].Show(False)
            state['mgmt_panel'].Layout()
            state['add_btn'].Enable()
            state['add_bundle_btn'].Enable()
            self._update_vst_buttons(state, effect_chain)

        if error:
            wx.MessageBox(
                _("Failed to load VST plugin:\n{}").format(error),
                _("VST Load Error"),
                wx.OK | wx.ICON_ERROR,
            )
        else:
            self._refresh_vst_list(state, effect_chain)
            new_idx = len(effect_chain.vst_slots) - 1
            state['listbox'].SetSelection(new_idx)
            self._on_vst_selected(state, effect_chain, chain_name)

    def _on_vst_add(self, state, effect_chain, chain_name, parent):
        wildcard = (
            "VST3 Plugins (*.vst3)|*.vst3"
            "|AU Plugins (*.component)|*.component"
            "|All Files (*.*)|*.*"
        )
        dlg = wx.FileDialog(
            self, _("Load VST Plugin"),
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        path = dlg.GetPath()
        dlg.Destroy()

        # pedalboard's load_plugin() must run on the main (UI) thread because
        # JUCE's VST3 host initialisation requires it, especially for reloads.
        # A background thread cannot be used here.
        #
        # wx.SafeYield() processes all pending paint/accessibility events so
        # that the loading label and busy cursor are rendered before the
        # blocking call freezes the GUI. This gives the user visible feedback.
        plugin_filename = os.path.basename(path)
        state['load_status'].SetLabel(_("Loading {}…").format(plugin_filename))
        state['load_status'].Show(True)
        state['mgmt_panel'].Layout()
        state['add_btn'].Disable()
        wx.BeginBusyCursor()
        wx.SafeYield(None, True)

        try:
            error = effect_chain.add_vst(path)
        finally:
            wx.EndBusyCursor()
            state['load_status'].SetLabel("")
            state['load_status'].Show(False)
            state['mgmt_panel'].Layout()
            state['add_btn'].Enable()
            self._update_vst_buttons(state, effect_chain)

        if error:
            wx.MessageBox(
                _("Failed to load VST plugin:\n{}").format(error),
                _("VST Load Error"),
                wx.OK | wx.ICON_ERROR,
            )
        else:
            self._refresh_vst_list(state, effect_chain)
            new_idx = len(effect_chain.vst_slots) - 1
            state['listbox'].SetSelection(new_idx)
            self._on_vst_selected(state, effect_chain, chain_name)

    def _on_vst_remove(self, state, effect_chain, chain_name):
        idx = state['listbox'].GetSelection()
        if idx == wx.NOT_FOUND:
            return
        name = effect_chain.vst_slots[idx]['name']
        dlg = wx.MessageDialog(
            self,
            _('Remove "{}"?').format(name),
            _("Remove VST Plugin"),
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if dlg.ShowModal() == wx.ID_YES:
            effect_chain.remove_vst(idx)
            self._refresh_vst_list(state, effect_chain)
            self._clear_vst_param_panel(state['param_scroll'], state['param_inner'])
            self._update_vst_buttons(state, effect_chain)
        dlg.Destroy()

    # ---- Parameter panel ----

    def _clear_vst_param_panel(self, scroll, inner_sizer):
        scroll.DestroyChildren()
        inner_sizer.Clear()
        scroll.FitInside()
        scroll.Layout()

    def _rebuild_vst_param_panel(self, scroll, inner_sizer,
                                  effect_chain, vst_index, chain_name, plugin_name):
        """Destroy and rebuild the parameter panel for the selected VST plugin."""
        scroll.DestroyChildren()
        inner_sizer.Clear()

        params = effect_chain.get_vst_parameters(vst_index)
        if not params:
            lbl = wx.StaticText(scroll, label=_("No parameters available."))
            inner_sizer.Add(lbl, 0, wx.ALL, 10)
        else:
            for param_name, param in params.items():
                widget = self._make_vst_param_widget(
                    scroll, effect_chain, vst_index, chain_name, plugin_name,
                    param_name, param)
                if widget is not None:
                    inner_sizer.Add(widget, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 3)

        scroll.FitInside()
        scroll.Layout()

    def _make_vst_param_widget(self, parent, effect_chain, vst_index,
                                chain_name, plugin_name, param_name, param):
        """Return an accessible sizer for one VST parameter, or None on error."""
        try:
            display_name = getattr(param, 'name', None) or param_name
            label_unit = getattr(param, 'label', '') or ''
            _min = getattr(param, 'min_value', None)
            _max = getattr(param, 'max_value', None)
            is_bool = getattr(param, 'is_boolean', False)
            is_discrete = getattr(param, 'is_discrete', False)
            valid_values = list(getattr(param, 'valid_values', None) or [])

            # pedalboard exposes current parameter values as attributes on the
            # plugin object (plugin.param_name), not on the metadata object.
            plugin = effect_chain.vst_slots[vst_index]['plugin']
            raw_current = getattr(plugin, param_name, None)

            # Some internal plugin parameters report None for their range.
            # Skip them unless they are boolean or discrete (no range needed).
            if not is_bool and not (valid_values and is_discrete):
                if _min is None or _max is None:
                    return None
            min_val = float(_min) if _min is not None else 0.0
            max_val = float(_max) if _max is not None else 1.0

            full_name = f"{chain_name}: {plugin_name}: {display_name}"
            slider_range = max_val - min_val if max_val != min_val else 1.0

            if is_bool:
                cb = wx.CheckBox(parent, label=display_name)
                cb.SetName(full_name)
                cb.SetValue(bool(raw_current) if raw_current is not None else False)

                def on_bool(event, pn=param_name):
                    effect_chain.set_vst_param(
                        vst_index, pn, 1.0 if event.IsChecked() else 0.0)
                cb.Bind(wx.EVT_CHECKBOX, on_bool)
                return cb

            if valid_values and is_discrete:
                str_vals = [str(v) for v in valid_values]
                row = wx.BoxSizer(wx.HORIZONTAL)
                lbl = wx.StaticText(parent, label=display_name + ":", size=(180, -1))
                row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
                choice = wx.Choice(parent, choices=str_vals)
                choice.SetName(full_name)
                str_cur = str(raw_current) if raw_current is not None else ''
                choice.SetSelection(str_vals.index(str_cur) if str_cur in str_vals else 0)

                def on_choice(event, pn=param_name, vals=valid_values):
                    try:
                        effect_chain.set_vst_param(vst_index, pn, vals[event.GetSelection()])
                    except (IndexError, Exception):
                        pass
                choice.Bind(wx.EVT_CHOICE, on_choice)
                row.Add(choice, 1, wx.EXPAND | wx.ALL, 3)
                return row

            # Float / int → slider mapped to 0-1000
            try:
                current_value = float(raw_current) if raw_current is not None else min_val
            except (TypeError, ValueError):
                current_value = min_val
            slider_val = int((current_value - min_val) / slider_range * 1000)
            slider_val = max(0, min(1000, slider_val))

            def fmt(v, mn=min_val, sr=slider_range, u=label_unit):
                real = mn + (v / 1000.0) * sr
                return (f"{real:.3g} {u}" if u else f"{real:.3g}").strip()

            def on_slide(v, pn=param_name, mn=min_val, sr=slider_range):
                effect_chain.set_vst_param(vst_index, pn, mn + (v / 1000.0) * sr)

            return self._make_slider(
                parent, display_name, f"{chain_name}: {plugin_name}",
                slider_val, 0, 1000, on_slide, fmt_func=fmt)

        except Exception as e:
            from utils.logger import get_logger
            get_logger('effects_dialog').error(
                f"Error creating VST param widget for {param_name}: {e}")
            return None

    # --- Reverb ---

    def _create_reverb_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Reverb"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Reverb')}")
        cb.SetValue(chain.reverb_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.reverb is not None:
            box.Add(self._make_slider(
                sb, _("Room Size"), name,
                int(chain.reverb.room_size * 100), 0, 100,
                lambda v: chain.set_reverb_param(room_size=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Damping"), name,
                int(chain.reverb.damping * 100), 0, 100,
                lambda v: chain.set_reverb_param(damping=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Wet Level"), name,
                int(chain.reverb.wet_level * 100), 0, 100,
                lambda v: chain.set_reverb_param(wet_level=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Dry Level"), name,
                int(chain.reverb.dry_level * 100), 0, 100,
                lambda v: chain.set_reverb_param(dry_level=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Width"), name,
                int(chain.reverb.width * 100), 0, 100,
                lambda v: chain.set_reverb_param(width=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.reverb_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('reverb', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- Delay ---

    def _create_delay_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Delay"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Delay')}")
        cb.SetValue(chain.delay_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.delay is not None:
            # Delay time: 0 to 2000 ms (mapped to 0.0 - 2.0 s)
            box.Add(self._make_slider(
                sb, _("Delay Time"), name,
                int(chain.delay.delay_seconds * 1000), 0, 2000,
                lambda v: chain.set_delay_param(delay_seconds=v / 1000.0),
                fmt_func=lambda v: f"{v} ms", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Feedback"), name,
                int(chain.delay.feedback * 100), 0, 95,
                lambda v: chain.set_delay_param(feedback=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Mix"), name,
                int(chain.delay.mix * 100), 0, 100,
                lambda v: chain.set_delay_param(mix=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.delay_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('delay', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- EQ ---

    def _create_eq_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Equalizer"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Equalizer')}")
        cb.SetValue(chain.eq_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.eq_low is not None:
            # EQ gains: -12 to +12 dB
            box.Add(self._make_slider(
                sb, _("Bass (200 Hz)"), name,
                int(chain.eq_low.gain_db), -12, 12,
                lambda v: chain.set_eq_param('low', gain_db=float(v)),
                fmt_func=lambda v: f"{v:+d} dB", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Mid (1 kHz)"), name,
                int(chain.eq_mid.gain_db), -12, 12,
                lambda v: chain.set_eq_param('mid', gain_db=float(v)),
                fmt_func=lambda v: f"{v:+d} dB", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Treble (8 kHz)"), name,
                int(chain.eq_high.gain_db), -12, 12,
                lambda v: chain.set_eq_param('high', gain_db=float(v)),
                fmt_func=lambda v: f"{v:+d} dB", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.eq_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('eq', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- Chorus ---

    def _create_chorus_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Chorus"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Chorus')}")
        cb.SetValue(chain.chorus_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.chorus is not None:
            # Rate: 0.1 to 10 Hz (slider 1-100 mapped to 0.1-10.0)
            box.Add(self._make_slider(
                sb, _("Rate"), name,
                int(chain.chorus.rate_hz * 10), 1, 100,
                lambda v: chain.set_chorus_param(rate_hz=v / 10.0),
                fmt_func=lambda v: f"{v / 10.0:.1f} Hz", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Depth"), name,
                int(chain.chorus.depth * 100), 0, 100,
                lambda v: chain.set_chorus_param(depth=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            box.Add(self._make_slider(
                sb, _("Mix"), name,
                int(chain.chorus.mix * 100), 0, 100,
                lambda v: chain.set_chorus_param(mix=v / 100.0),
                fmt_func=lambda v: f"{v}%", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.chorus_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('chorus', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- Compressor ---

    def _create_compressor_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Compressor"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Compressor')}")
        cb.SetValue(chain.compressor_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.compressor is not None:
            # Threshold: -60 to 0 dB
            box.Add(self._make_slider(
                sb, _("Threshold"), name,
                int(chain.compressor.threshold_db), -60, 0,
                lambda v: chain.set_compressor_param(threshold_db=float(v)),
                fmt_func=lambda v: f"{v} dB", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            # Ratio: 1 to 20 (slider 10-200, mapped to 1.0-20.0)
            box.Add(self._make_slider(
                sb, _("Ratio"), name,
                int(chain.compressor.ratio * 10), 10, 200,
                lambda v: chain.set_compressor_param(ratio=v / 10.0),
                fmt_func=lambda v: f"{v / 10.0:.1f}:1", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            # Attack: 0.1 to 100 ms (slider 1-1000, mapped to 0.1-100.0)
            box.Add(self._make_slider(
                sb, _("Attack"), name,
                int(chain.compressor.attack_ms * 10), 1, 1000,
                lambda v: chain.set_compressor_param(attack_ms=v / 10.0),
                fmt_func=lambda v: f"{v / 10.0:.1f} ms", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            # Release: 1 to 500 ms
            box.Add(self._make_slider(
                sb, _("Release"), name,
                int(chain.compressor.release_ms), 1, 500,
                lambda v: chain.set_compressor_param(release_ms=float(v)),
                fmt_func=lambda v: f"{v} ms", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.compressor_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('compressor', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- Limiter ---

    def _create_limiter_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Limiter"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Limiter')}")
        cb.SetValue(chain.limiter_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.limiter is not None:
            # Threshold: -30 to 0 dB
            box.Add(self._make_slider(
                sb, _("Threshold"), name,
                int(chain.limiter.threshold_db), -30, 0,
                lambda v: chain.set_limiter_param(threshold_db=float(v)),
                fmt_func=lambda v: f"{v} dB", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

            # Release: 1 to 500 ms
            box.Add(self._make_slider(
                sb, _("Release"), name,
                int(chain.limiter.release_ms), 1, 500,
                lambda v: chain.set_limiter_param(release_ms=float(v)),
                fmt_func=lambda v: f"{v} ms", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.limiter_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('limiter', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- Gain ---

    def _create_gain_section(self, parent, chain, name):
        section_panel = wx.Panel(parent)
        section_sizer = wx.BoxSizer(wx.VERTICAL)
        box = wx.StaticBoxSizer(wx.VERTICAL, section_panel, _("Gain"))
        sb = box.GetStaticBox()
        sliders = []

        cb = wx.CheckBox(sb, label=_("Enable"))
        cb.SetName(f"{name}: {_('Enable Gain')}")
        cb.SetValue(chain.gain_enabled)
        box.Add(cb, 0, wx.ALL, 5)

        if chain.gain is not None:
            # Gain: -24 to +24 dB
            box.Add(self._make_slider(
                sb, _("Gain"), name,
                int(chain.gain.gain_db), -24, 24,
                lambda v: chain.set_gain_param(gain_db=float(v)),
                fmt_func=lambda v: f"{v:+d} dB", collect=sliders),
                0, wx.EXPAND | wx.ALL, 3)

        self._set_sliders_enabled(sliders, chain.gain_enabled)
        cb.Bind(wx.EVT_CHECKBOX, lambda e, s=sliders: (
            chain.enable_effect('gain', e.IsChecked()),
            self._set_sliders_enabled(s, e.IsChecked())))

        section_sizer.Add(box, 1, wx.EXPAND)
        section_panel.SetSizer(section_sizer)
        return section_panel

    # --- Slider helper ---

    @staticmethod
    def _set_sliders_enabled(sliders, enabled):
        """Enable or disable a list of sliders."""
        for s in sliders:
            s.Enable(enabled)

    def _make_slider(self, parent, label, chain_name, value, min_val, max_val,
                     callback, fmt_func=None, collect=None):
        """
        Create a labeled slider with value display.

        Args:
            parent: Parent window
            label: Parameter label text
            chain_name: Name of the effect chain (for accessibility)
            value: Initial slider value
            min_val: Minimum slider value
            max_val: Maximum slider value
            callback: Function called with slider value on change
            fmt_func: Optional function to format the display value
            collect: Optional list to append the slider widget to
        """
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        lbl = wx.StaticText(parent, label=label + ":", size=(120, -1))
        sizer.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        if fmt_func is None:
            fmt_func = lambda v: str(v)

        slider = wx.Slider(parent, value=value, minValue=min_val, maxValue=max_val,
                           style=wx.SL_HORIZONTAL)
        slider.SetName(f"{chain_name}: {label}")
        if sys.platform == 'win32':
            slider.SetAccessible(_FormattedSliderAccessible(slider, fmt_func))
        sizer.Add(slider, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)

        val_lbl = wx.StaticText(parent, label=fmt_func(value), size=(70, -1),
                                style=wx.ALIGN_RIGHT)
        if sys.platform == 'win32':
            val_lbl.SetAccessible(_ValueDisplayAccessible(val_lbl))
        sizer.Add(val_lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        def on_slider(event):
            v = slider.GetValue()
            val_lbl.SetLabel(fmt_func(v))
            callback(v)

        slider.Bind(wx.EVT_SLIDER, on_slider)

        if collect is not None:
            collect.append(slider)

        return sizer
