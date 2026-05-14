"""
Universal list class to choose between ListCtrl and DataViewListCtrl
"""
import wx
import wx.dataview as dv
import sys



class UniversalListCtrl:
    """
    Cross-platform list wrapper with optional checkbox support.

    wx.ListCtrl is used on Windows, while wx.dataview.DataViewListCtrl is used
    on Linux and macOS for better accessibility. The wrapper normalizes the
    small subset of list operations used by the application.
    """

    EVT_ITEM_CHECKED = wx.NewEventType()

    def __init__(
        self,
        parent,
        size=wx.DefaultSize,
        style=wx.LC_REPORT | wx.BORDER_SUNKEN,
        checkboxes=False,
        force_dataview=False
    ):
        """
        Initialize universal list control.

        Args:
            parent: Parent wx window.
            size: Initial control size.
            style: wx style flags applied to the underlying list control.
            checkboxes: Whether rows should support checked/unchecked state.
            force_dataview: Force DataViewListCtrl even on platforms that would
                normally use wx.ListCtrl.
        """
        # We use DataViewListCtrl for Linux and macOS unless forced (better accessibility)
        self.use_dataview = sys.platform.startswith('linux') or sys.platform == 'darwin' or force_dataview
        self.checkboxes = checkboxes
        self._checkbox_column = None

        if self.use_dataview:
            self.control = dv.DataViewListCtrl(parent, style=style, size=size)
        else:
            self.control = wx.ListCtrl(parent, style=style, size=size)
            if self.checkboxes:
                self.control.EnableCheckBoxes()

    def InsertColumn(self, col, heading, width=wx.LIST_AUTOSIZE, checkbox=False):
        """
        Insert a column in the underlying control.

        Args:
            col: Zero-based column index.
            heading: Text shown in the column header.
            width: Column width or wx autosize constant.
            checkbox: Whether this column stores checkbox/toggle values.
        """
        if self.use_dataview:
            if checkbox:
                self.control.AppendToggleColumn(
                    heading,
                    mode=dv.DATAVIEW_CELL_ACTIVATABLE,
                    width=width
                )
                self._checkbox_column = col
            else:
                self.control.AppendTextColumn(heading, width=width)
        else:
            self.control.InsertColumn(col, heading, width=width)
            if checkbox:
                self._checkbox_column = col

    def Append(self, entry):
        """
        Adds a row to the list.
        'entry' must be a list or tuple of values matching the column count.

        Args:
            entry: Sequence of row values. Checkbox columns should contain
                truthy or falsy values; text columns are converted to strings.
        """
        if self.use_dataview:
            # DataViewListCtrl.AppendItem expects exactly one argument: a sequence
            # Keep toggle columns as bool and format text columns as strings.
            formatted_entry = [
                bool(item) if col_idx == self._checkbox_column else str(item)
                for col_idx, item in enumerate(entry)
            ]
            self.control.AppendItem(formatted_entry)
        else:
            # ListCtrl: Insert the first item, then set sub-items
            index = self.control.GetItemCount()
            if self._checkbox_column == 0:
                self.control.InsertItem(index, "")
                self.control.CheckItem(index, bool(entry[0]))
                text_start_col = 1
            else:
                self.control.InsertItem(index, str(entry[0]))
                text_start_col = 1
            for col_idx in range(text_start_col, len(entry)):
                self.control.SetItem(index, col_idx, str(entry[col_idx]))

    def Bind(self, event_type, handler):
        """
        Unifies binding for common list events.

        Args:
            event_type: wx event binder or UniversalListCtrl event type.
            handler: Callable that receives the normalized event.
        """
        if event_type == wx.EVT_LIST_ITEM_SELECTED:
            if self.use_dataview:
                # Map DataView selection to List selection logic
                self.control.Bind(dv.EVT_DATAVIEW_SELECTION_CHANGED, 
                                  lambda evt: self._handle_selection(evt, handler))
            else:
                self.control.Bind(wx.EVT_LIST_ITEM_SELECTED, handler)
        
        elif event_type in [wx.EVT_CONTEXT_MENU, wx.EVT_CHAR_HOOK]:
            # These are standard wx.Window events, no mapping needed
            self.control.Bind(event_type, handler)

        elif event_type == self.EVT_ITEM_CHECKED:
            if self.use_dataview:
                self.control.Bind(
                    dv.EVT_DATAVIEW_ITEM_VALUE_CHANGED,
                    lambda evt: self._handle_check(evt, handler)
                )
            else:
                self.control.Bind(
                    wx.EVT_LIST_ITEM_CHECKED,
                    lambda evt: self._handle_check(evt, handler)
                )
                self.control.Bind(
                    wx.EVT_LIST_ITEM_UNCHECKED,
                    lambda evt: self._handle_check(evt, handler)
                )
        
        else:
            # Fallback for other events
            self.control.Bind(event_type, handler)

    def _handle_selection(self, evt, user_handler):
        """
        Internal helper to normalize DataViewEvent so it feels 
        closer to a ListEvent for the handler.

        Args:
            evt: Native DataView selection event.
            user_handler: Original event handler supplied by the caller.
        """
        # Accessibility: Ensure screen reader focus remains stable 
        # while processing selection logic.
        if self.use_dataview:
            item = evt.GetItem()
            if item.IsOk():
                # We can inject a 'GetIndex' method into the event object
                # to mimic ListEvent if necessary, or just call the handler.
                evt.GetIndex = lambda: self.control.ItemToRow(item)
        
        user_handler(evt)

    def _handle_check(self, evt, user_handler):
        """
        Normalize checkbox/toggle events across ListCtrl and DataViewListCtrl.

        Args:
            evt: Native checkbox or DataView value-changed event.
            user_handler: Original event handler supplied by the caller.
        """
        row = -1
        checked = False

        if self.use_dataview:
            if evt.GetColumn() != self._checkbox_column:
                evt.Skip()
                return
            item = evt.GetItem()
            if item.IsOk():
                row = self.control.ItemToRow(item)
                checked = self.control.GetToggleValue(row, self._checkbox_column)
        else:
            row = evt.GetIndex()
            checked = self.control.IsItemChecked(row)

        evt.GetIndex = lambda: row
        evt.IsChecked = lambda: checked
        user_handler(evt)

    def GetSelectedRow(self):
        """
        Return the currently selected row index.

        Returns:
            int: Selected row index, or -1 when no row is selected.
        """
        if self.use_dataview:
            item = self.control.GetSelection()
            return self.control.ItemToRow(item) if item.IsOk() else -1
        else:
            return self.control.GetFirstSelected()

    def GetItemCount(self):
        """
        Return the total number of items in the list.

        Returns:
            int: Number of rows in the underlying control.
        """
        return self.control.GetItemCount()

    def SelectRow(self, index):
        """
        Selects and focuses a row by index.

        Args:
            index: Zero-based row index to select.
        """
        if index < 0 or index >= self.GetItemCount():
            return

        if self.use_dataview:
            # Try to avoid ATK noise
            if self.control.GetColumnCount() > 0:
                item = self.control.RowToItem(index)
                if item.IsOk():
                    self.control.Select(item)
                    self.control.EnsureVisible(item)
        else:
            self.control.Select(index)
            self.control.Focus(index)

    def SetChecked(self, index, checked):
        """
        Set a row checkbox/toggle value without changing selection.

        Args:
            index: Zero-based row index to update.
            checked: New checked state.
        """
        if self._checkbox_column is None or index < 0 or index >= self.GetItemCount():
            return

        if self.use_dataview:
            self.control.SetToggleValue(bool(checked), index, self._checkbox_column)
        else:
            self.control.CheckItem(index, bool(checked))

    def IsChecked(self, index):
        """
        Return the row checkbox/toggle state.

        Args:
            index: Zero-based row index to inspect.

        Returns:
            bool: True when the row is checked, otherwise False.
        """
        if self._checkbox_column is None or index < 0 or index >= self.GetItemCount():
            return False

        if self.use_dataview:
            return self.control.GetToggleValue(index, self._checkbox_column)
        return self.control.IsItemChecked(index)

    def GetControl(self):
        """
        Return the wrapped wx control.

        Returns:
            wx.Window: Underlying wx.ListCtrl or DataViewListCtrl instance.
        """
        return self.control
