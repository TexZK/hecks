# Copyright (c) 2021, Andrea Zoppi. All rights reserved.
#
# This file is part of Hecks.
#
# Hecks is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Hecks is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Hecks.  If not, see <https://www.gnu.org/licenses/>.

import pkgutil
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
import tkinter.simpledialog
from math import floor
from tkinter import ttk

import ttkthemes
from typing import Any
from typing import Callable
from typing import MutableMapping
from typing import Optional
from typing import Tuple
from typing import Union
from typing import cast as _cast

from bytesparse.base import Address
from hexrec.formats.asciihex import AsciiHexFile
from hexrec.formats.avr import AvrFile
from hexrec.formats.ihex import IhexFile
from hexrec.formats.mos import MosFile
from hexrec.formats.raw import RawFile
from hexrec.formats.srec import SrecFile
from hexrec.formats.titxt import TiTxtFile
from hexrec.formats.xtek import XtekFile

from .common import ADDRESS_BITS
from .common import BYTE_ENCODINGS
from .common import LINE_LENGTHS
from .common import PROGRAM_TITLE
from .common import BaseInstanceManager
from .common import BaseEditorWidget
from .common import BaseEngine
from .common import BaseUserInterface
from .common import CellCoord
from .common import CellCoords
from .common import CharCoord
from .common import CharCoords
from .common import CursorMode
from .common import EngineStatus
from .common import FloatCoords
from .common import SelectionMode
from .engine import Engine
from .utils import HEX_SET
from .utils import ValueFormatEnum
from .utils import parse_int


# =====================================================================================================================

PixelCoord = int
PixelCoords = Tuple[PixelCoord, PixelCoord]

CanvasObject = int


_THEME: str = 'black'
_COLOR_BG: str = 'SystemWindow'
_COLOR_FG: str = 'SystemWindowText'
_COLOR_OG: str = 'grey25'
_COLOR_CUR: str = 'red'
_COLOR_SEL_BG: str = 'SystemHighlight'
_COLOR_SEL_FG: str = 'SystemHighlightText'
_COLOR_SEL_OG: str = 'grey75'

_TOOLTIP_FONT: Union[Tuple[str, int], str] = 'TkTooltipFont'
_TOOLTIP_FG: str = 'SystemButtonText'
_TOOLTIP_BG: str = 'lightyellow'
_TOOLTIP_CLEARANCE: PixelCoords = (5, 50)


def _is_shift_in_event(event: Any = None) -> bool:
    return (event.state & 1) != 0 if event else False


def _fix_global_colors(root: ttkthemes.ThemedTk) -> None:
    global _COLOR_BG
    global _COLOR_FG
    global _COLOR_OG
    global _COLOR_SEL_FG
    global _COLOR_SEL_BG
    global _COLOR_SEL_OG
    global _TOOLTIP_FG
    global _TOOLTIP_BG
    ttk_style = ttk.Style()

    bg_color = ttk_style.lookup('TLabelFrame', 'background') or _COLOR_BG
    _COLOR_BG = bg_color
    bg_rgb = root.winfo_rgb(bg_color)

    fg_color = ttk_style.lookup('TLabelFrame', 'foreground') or _COLOR_FG
    _COLOR_FG = fg_color
    fg_rgb = root.winfo_rgb(fg_color)

    _COLOR_OG = mix_color_hex(*fg_rgb, *bg_rgb, 0.25)

    sel_bg_color = ttk_style.lookup('TEntry', 'selectbackground') or _COLOR_SEL_BG
    _COLOR_SEL_BG = sel_bg_color
    sel_bg_rgb = root.winfo_rgb(sel_bg_color)

    sel_fg_color = ttk_style.lookup('TEntry', 'selectforeground') or _COLOR_SEL_FG
    _COLOR_SEL_FG = sel_fg_color
    sel_fg_rgb = root.winfo_rgb(sel_fg_color)

    _COLOR_SEL_OG = mix_color_hex(*sel_fg_rgb, *sel_bg_rgb, 0.25)

    _TOOLTIP_FG = _COLOR_SEL_FG
    _TOOLTIP_BG = _COLOR_SEL_BG


def mix_color_hex(x_r, x_g, x_b, y_r, y_g, y_b, m) -> str:
    r = (max(0, min(int(((1 - m) * x_r) + (m * y_r)), 65535)) + 128) // 256
    g = (max(0, min(int(((1 - m) * x_g) + (m * y_g)), 65535)) + 128) // 256
    b = (max(0, min(int(((1 - m) * x_b) + (m * y_b)), 65535)) + 128) // 256
    c = f'#{r:02X}{g:02X}{b:02X}'
    return c


# =====================================================================================================================

_image_cache = {}


def load_image(path: str) -> tk.PhotoImage:
    global _image_cache
    image = _image_cache.get(path)
    if image is None:
        # See: https://stackoverflow.com/a/58941536
        data = pkgutil.get_data(__name__, path)
        image = tk.PhotoImage(data=data)
        _image_cache[path] = image
    return image


# =====================================================================================================================

def __merge_extensions(hexrec_format):
    extensions = hexrec_format.FILE_EXT
    return ';'.join(f'*{ext}' for ext in extensions)


FILE_TYPES = (
    ('Raw binary', __merge_extensions(RawFile)),
    ('ASCII-HEX', __merge_extensions(AsciiHexFile)),
    ('Atmel Generic AVR', __merge_extensions(AvrFile)),
    ('Intel HEX', __merge_extensions(IhexFile)),
    ('MOS Technology', __merge_extensions(MosFile)),
    ('Motorola S-record', __merge_extensions(SrecFile)),
    ('TI-TXT', __merge_extensions(TiTxtFile)),
    ('Tektronix Extended', __merge_extensions(XtekFile)),
    ('All files', '*'),
)


# =====================================================================================================================

class Tooltip:

    def __init__(
        self,
        widget: ttk.Widget,
        text: str = '',
        time: int = 2000,
        font: Union[Tuple[str, int], str] = _TOOLTIP_FONT,
        fg: Optional[str] = None,
        bg: Optional[str] = None,
        clearance_x: int = _TOOLTIP_CLEARANCE[0],
        clearance_y: int = _TOOLTIP_CLEARANCE[1],
    ):
        self._widget = widget
        self._text = text
        self._time = time
        self._font = font
        self._fg = fg or _TOOLTIP_FG
        self._bg = bg or _TOOLTIP_BG
        self._clearance_x = clearance_x
        self._clearance_y = clearance_y
        self._tooltip: Optional[tk.Toplevel] = None

        widget.focus_displayof()
        widget.bind('<Enter>', self._enter)
        widget.bind('<Leave>', self._leave)

    @property
    def widget(self) -> ttk.Widget:
        return self._widget

    def config(
        self,
        text: Optional[str] = None,
        time: Optional[int] = None,
        font: Optional[str] = None,
        fg: Optional[str] = None,
        bg: Optional[str] = None,
        clearance_x: Optional[int] = None,
        clearance_y: Optional[int] = None,
    ) -> None:
        if text is not None:
            self._text = text
        if time is not None:
            self._time = time
        if font is not None:
            self._font = font
        if fg is not None:
            self._fg = fg
        if bg is not None:
            self._bg = bg
        if clearance_x is not None:
            self._clearance_x = clearance_x
        if clearance_y is not None:
            self._clearance_y = clearance_y

    def _enter(self, event=None):
        widget = self._widget
        tooltip = self._tooltip

        if tooltip is None:
            tooltip = tk.Toplevel(widget)
            self._tooltip = tooltip
            tooltip.overrideredirect(True)

            label = tk.Label(tooltip, text=self._text, fg=self._fg, bg=self._bg,
                                  relief=tk.RIDGE, borderwidth=1, font=self._font)
            label.pack(ipadx=5)

        tooltip.update_idletasks()

        screen_w = widget.winfo_screenwidth()
        screen_h = widget.winfo_screenheight()

        widget_x = widget.winfo_rootx()
        widget_y = widget.winfo_rooty()
        widget_w = widget.winfo_width()
        widget_h = widget.winfo_height()

        tooltip_w = tooltip.winfo_width()
        tooltip_h = tooltip.winfo_height()

        clearance_x = self._clearance_x
        clearance_y = self._clearance_y

        if widget_x + widget_w + clearance_x + tooltip_w < screen_w:
            x = widget_x + clearance_x  # widget match
        else:
            x = widget_x + clearance_x - tooltip_w  # widget left

        if widget_y + clearance_y + tooltip_h < screen_h:
            y = widget_y + widget_h  # below widget
        else:
            y = widget_y - tooltip_h  # above widget

        tooltip.wm_geometry(f'{x:+d}{y:+d}')

        if self._time:
            tooltip.after(self._time, self._leave)

    def _leave(self, event=None):
        tooltip = self._tooltip
        if tooltip is not None:
            tooltip.destroy()
            self._tooltip = None


# =====================================================================================================================

class ToolbarTray(ttk.Frame):

    def __init__(self, parent, text_kwargs=None, **kwargs):
        d = dict(
            # highlightthickness=0,  # missing with ttk
            takefocus=0,
        )
        d.update(kwargs)
        kwargs = d
        super().__init__(parent, **kwargs)
        self.pack_propagate(False)

        if text_kwargs is None:
            text_kwargs = {}
        text_kwargs.setdefault('width', 1)
        text_kwargs.setdefault('height', 1)
        text_kwargs.setdefault('padx', 0)
        text_kwargs.setdefault('pady', 0)
        # text_kwargs.setdefault('highlightthickness', 0)  # missing with ttk
        text_kwargs.setdefault('insertborderwidth', 0)
        text_kwargs.setdefault('selectborderwidth', 0)
        text_kwargs.setdefault('bg', _COLOR_BG)
        text_kwargs.setdefault('takefocus', 0)
        text_kwargs.setdefault('spacing1', 0)
        text_kwargs.setdefault('spacing2', 0)
        text_kwargs.setdefault('spacing3', 0)
        if 'borderwidth' not in text_kwargs and 'bd' not in text_kwargs:
            text_kwargs.setdefault('borderwidth', 0)

        container = tk.Text(self, **text_kwargs)
        self._container = container
        container.pack(side=tk.TOP, expand=True, fill=tk.BOTH)
        self._bg = text_kwargs['bg']

        container.configure(bg=self._bg, cursor='arrow', state=tk.DISABLED)
        container.bind('<Key>', lambda _: 'break')
        container.bind('<1>', lambda _: 'break')

        self.bind('<Configure>', self._on_configure)

    def add_widget(self, widget):
        self._container.window_create(tk.INSERT, window=widget)

    def _on_configure(self, event=None, force=False):
        self.update_idletasks()
        container = self._container
        container.configure(bg=self._bg)

        borderwidth = self.cget('borderwidth')
        widget_height = self.winfo_height()
        content_height = container.count('1.0', tk.END, 'update', 'ypixels')
        height = content_height + (borderwidth * 2)

        if widget_height != height or force:
            self.configure(height=height)


# ---------------------------------------------------------------------------------------------------------------------

class Toolbar(ttk.Frame):

    def __init__(self, parent, **kwargs):
        if 'borderwidth' not in kwargs and 'bd' not in kwargs:
            kwargs.setdefault('borderwidth', 1)
        kwargs.setdefault('relief', tk.RIDGE)
        super().__init__(parent, **kwargs)

        self._widgets: MutableMapping[Any, ttk.Widget] = {}
        self._tooltips: MutableMapping[Any, Tooltip] = {}

    @property
    def widget_count(self) -> int:
        return len(self._widgets)

    def get_widget(self, name: str) -> ttk.Widget:
        return self._widgets[name]

    def add_widget(
        self, widget: ttk.Widget,
        key: Any = None,
        tooltip: Optional[str] = None,
    ) -> ttk.Widget:

        self._widgets[key] = widget
        if tooltip and key is None:
            key = tooltip
        if tooltip:
            self._tooltips[key] = Tooltip(widget, text=tooltip)
        return widget

    def add_button(
        self,
        key: Any = None,
        tooltip: Optional[str] = None,
        **kwargs
    ) -> ttk.Widget:

        if tooltip and not key:
            key = tooltip
        kwargs.setdefault('style', 'Toolbutton')
        kwargs.setdefault('takefocus', 0)
        widget = ttk.Button(self, **kwargs)
        self.add_widget(widget, key=key, tooltip=tooltip)
        return widget

    def add_separator(self, **kwargs) -> ttk.Widget:
        kwargs.setdefault('orient', tk.VERTICAL)
        widget = ttk.Separator(self, **kwargs)
        key = -self.widget_count  # separators have negative integer key
        self.add_widget(widget, key=key)
        return widget

    def finalize(self, pad_x: int = 4, pad_y: int = 1, pad_y_sep: int = 4) -> None:
        last = self.widget_count - 1

        for index, (key, widget) in enumerate(self._widgets.items()):
            pad_l = 0
            pad_r = 0
            pad_v = pad_y
            sticky = None

            if isinstance(key, int):
                if key < 0:
                    pad_l = pad_x
                    pad_r = pad_x
                    pad_v = pad_y_sep
                    sticky = tk.NS

            else:
                pad_l = pad_x if index <= 0 else 0
                pad_r = pad_x if index >= last else 0
                pad_v = pad_y
                sticky = tk.NS

            widget.grid(row=0, column=index, padx=(pad_l, pad_r), pady=pad_v, sticky=sticky)


# =====================================================================================================================

class EditorWidget(BaseEditorWidget, ttk.Frame):

    def __init__(
        self,
        parent,
        engine: BaseEngine,
        status: EngineStatus,
        width: PixelCoord = 200,
        height: PixelCoord = 100,
        pad_x: int = 4,
        pad_y: int = 2,
        **kwargs: Any,
    ):
        self._engine = engine
        self._status = status  # read-only

        kwargs.setdefault('padding', (0, 0))
        ttk.Frame.__init__(self, parent, width=width, height=height, **kwargs)

        BaseEditorWidget.__init__(self)

        self.__init_misc(pad_x, pad_y)
        self.__init_address_bar()
        self.__init_offset_bar()
        self.__init_cells_view()
        self.__init_chars_view()
        self.__init_cursor()
        self.__init_layout()
        self.__init_bindings()

        self.on_cells_focus_out()

    def __init_misc(self, pad_x: PixelCoord, pad_y: PixelCoord) -> None:
        self._pad_x = pad_x
        self._pad_y = pad_y

        font = tk.font.Font(font=('Consolas', 10))
        font_w = font.measure('#')
        font_h = font.metrics('linespace')

        self._font = font
        self._font_w = font_w
        self._font_h = font_h

        status = self._status
        line_length = status.line_length
        cell_format_length = status.cell_format_length
        cell_spacing = status.cell_spacing
        offset_format_length = status.offset_format_length
        offset_spacing = status.offset_spacing

        offset_w = pad_x + (font_w * (line_length * (offset_format_length + offset_spacing) - 1)) + pad_x
        view_w = pad_x + (font_w * (line_length * (cell_format_length + cell_spacing) - 1)) + pad_x
        self._view_w = max(offset_w, view_w)

        self._sel_start_address_prev: Address = -1  # dummy
        self._sel_endin_address_prev: Address = -1  # dummy

    def __init_address_bar(self) -> None:
        pad_x, pad_y = self._pad_x, self._pad_y
        font_w, font_h = self._font_w, self._font_h
        address_format_length = self._status.address_format_length

        address_skip_label = ttk.Label(self, anchor=tk.NW, font=self._font, padding=(pad_x, pad_y), borderwidth=0)
        self._address_skip_label = address_skip_label
        Tooltip(address_skip_label, text='Address skip')

        address_canvas_w = pad_x + (font_w * address_format_length) + pad_x
        address_canvas_h = pad_y + (font_h * 16) + pad_y
        self._address_canvas_size: PixelCoords = (address_canvas_w, address_canvas_h)

        address_canvas = tk.Canvas(self, width=address_canvas_w, height=address_canvas_h,
                                        bg=_COLOR_BG, borderwidth=0, highlightthickness=0)
        self._address_canvas = address_canvas
        self._address_canvas_w: PixelCoord = address_canvas_w

        self._addrs_text_id: MutableMapping[CellCoord, CanvasObject] = {}

    def __init_offset_bar(self) -> None:
        pad_x, pad_y = self._pad_x, self._pad_y
        font_w, font_h = self._font_w, self._font_h
        font = self._font

        offset_w = self._view_w
        offset_h = pad_y + font_h + pad_y
        self._offset_canvas_size: PixelCoords = (offset_w, offset_h)

        offset_canvas = tk.Canvas(self, width=offset_w, height=offset_h,
                                       bg=_COLOR_BG, borderwidth=0, highlightthickness=0,
                                       scrollregion=(0, 0, offset_w, 1))
        self._offset_canvas = offset_canvas

        offset_text_id: CanvasObject = offset_canvas.create_text(1 + pad_x, pad_y, text='', anchor=tk.NW,
                                                                 font=font, fill=_COLOR_FG)
        self._offset_text_id = offset_text_id

    def __init_cells_view(self) -> None:
        pad_y = self._pad_y
        font_h = self._font_h
        view_w = self._view_w
        view_h = pad_y + (font_h * 16) + pad_y
        self._cells_pixel_size: PixelCoords = (view_w, view_h)
        self._cells_pixel_x: PixelCoord = 0  # dummy
        self._cells_pixel_y: PixelCoord = 0  # dummy
        self._cells_pixel_y_prev: PixelCoord = -1  # dummy

        cells_canvas = tk.Canvas(self, width=view_w, height=view_h, borderwidth=1, highlightthickness=0,
                                      relief=tk.SUNKEN, bg=_COLOR_BG, cursor='xterm',
                                      scrollregion=(0, 0, view_w, 1), takefocus=1)
        self._cells_canvas = cells_canvas

        self._cells_text_id: MutableMapping[CellCoords, CanvasObject] = {}
        self._cells_rect_id: MutableMapping[CellCoords, CanvasObject] = {}

        cells_vbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
        cells_vbar.set(0, 1)
        cells_vbar.configure(command=self._on_vbar)
        self._cells_vbar: ttk.Scrollbar = cells_vbar

        cells_hbar = ttk.Scrollbar(self, orient=tk.HORIZONTAL)
        cells_hbar.configure(command=self._on_hbar)
        cells_canvas.configure(xscrollcommand=cells_hbar.set)
        self._offset_canvas.configure(xscrollcommand=cells_hbar.set)
        self._cells_hbar: ttk.Scrollbar = cells_hbar

        # Cell status cache, faster than Tk
        self._cells_dirty: set = set()
        self._cells_pixel: MutableMapping[CellCoords, PixelCoords] = {}
        self._cells_selected: set = set()
        self._cells_text_str: MutableMapping[CellCoords, str] = {}

    def __init_chars_view(self) -> None:
        pad_x = self._pad_x
        font_w = self._font_w
        status = self._status
        line_length = status.line_length

        chars_w = pad_x + (font_w * line_length) + pad_x
        chars_h = self._cells_pixel_size[1]
        chars_canvas = tk.Canvas(self, width=chars_w, height=chars_h, borderwidth=1, highlightthickness=0,
                                      relief=tk.SUNKEN, bg=_COLOR_BG, cursor='xterm',
                                      scrollregion=(0, 0, chars_w, 1), takefocus=1)
        self._chars_canvas = chars_canvas

        self._chars_text_id: MutableMapping[CellCoords, CanvasObject] = {}
        self._chars_rect_id: MutableMapping[CellCoords, CanvasObject] = {}

        chars_hbar = ttk.Scrollbar(self, orient=tk.HORIZONTAL)
        chars_hbar.configure(command=chars_canvas.xview)
        chars_canvas.configure(xscrollcommand=chars_hbar.set)
        self._chars_hbar: ttk.Scrollbar = chars_hbar

        self._chars_title = ttk.Label(self, text='Text', anchor=tk.W)

    def __init_layout(self) -> None:
        self._address_skip_label.grid(row=0, column=0, sticky=tk.EW)
        self._offset_canvas.grid(row=0, column=1, sticky=tk.EW)
        self._chars_title.grid(row=0, column=3, sticky=tk.EW)

        self._address_canvas.grid(row=1, column=0, sticky=tk.NSEW)
        self._cells_canvas.grid(row=1, column=1, sticky=tk.NSEW)
        self._cells_vbar.grid(row=1, column=2, sticky=tk.NS)
        self._chars_canvas.grid(row=1, column=3, sticky=tk.NSEW)

        self._cells_hbar.grid(row=2, column=1, sticky=tk.EW)
        self._chars_hbar.grid(row=2, column=3, sticky=tk.EW)

        self.rowconfigure(1, weight=1)
        self.columnconfigure(1, weight=6, minsize=64)
        self.columnconfigure(3, weight=1, minsize=64)

    def __init_cursor(self) -> None:
        color = _COLOR_FG

        self._cells_cursor_color: str = color
        cells_cursor_id = self._cells_canvas.create_line(-2, -2, -1, -1, width=2, fill=color, tags='cursor')
        self._cells_cursor_id: CanvasObject = cells_cursor_id

        self._chars_cursor_color: str = color
        chars_cursor_id = self._chars_canvas.create_line(-2, -2, -1, -1, width=2, fill=color, tags='cursor')
        self._chars_cursor_id: CanvasObject = chars_cursor_id

    def __init_bindings(self) -> None:

        control_bindings = {
            '<plus>':                  self.on_key_reserve_cell,
            '<minus>':                 self.on_key_delete_cell,
            '<period>':                self.on_key_clear_cell,
            '<BackSpace>':             self.on_key_clear_back,
            '<comma>':                 self.on_key_clear_next,
            '<Delete>':                self.on_key_delete,
            '$':                       self.on_key_fill,
            '%':                       self.on_key_flood,

            '<Control-x>':             self.on_key_cut,
            '<Shift-Delete>':          self.on_key_cut,

            '<Control-c>':             self.on_key_copy,
            '<Control-C>':             self.on_key_copy,
            '<Control-Insert>':        self.on_key_copy,

            '<Control-v>':             self.on_key_paste,
            '<Control-V>':             self.on_key_paste,
            '<Shift-Insert>':          self.on_key_paste,

            '<Control-k>':             self.on_key_crop,

            '<Control-m>':             self.on_key_move_focus,
            '<Control-M>':             self.on_key_move_apply,

            '<Control-Up>':            self.on_key_scroll_line_up,
            '<Control-Prior>':         self.on_key_scroll_page_up,

            '<Control-Down>':          self.on_key_scroll_line_down,
            '<Control-Next>':          self.on_key_scroll_page_down,

            '<Control-Alt-Up>':        self.on_key_scroll_top,
            '<Control-Alt-Down>':      self.on_key_scroll_bottom,

            '<Left>':                  self.on_key_move_left_digit,
            '<Shift-Left>':            self.on_key_move_left_digit,

            '<Control-Left>':          self.on_key_move_left_byte,
            '<Control-Shift-Left>':    self.on_key_move_left_byte,

            '<Alt-Left>':              self.on_key_goto_block_previous,
            '<Alt-Shift-Left>':        self.on_key_goto_block_previous,

            '<Right>':                 self.on_key_move_right_digit,
            '<Shift-Right>':           self.on_key_move_right_digit,

            '<Control-Right>':         self.on_key_move_right_byte,
            '<Control-Shift-Right>':   self.on_key_move_right_byte,

            '<Alt-Right>':             self.on_key_goto_block_next,
            '<Alt-Shift-Right>':       self.on_key_goto_block_next,

            '<Up>':                    self.on_key_move_line_up,
            '<Shift-Up>':              self.on_key_move_line_up,

            '<Prior>':                 self.on_key_move_page_up,
            '<Shift-Prior>':           self.on_key_move_page_up,

            '<Down>':                  self.on_key_move_line_down,
            '<Shift-Down>':            self.on_key_move_line_down,

            '<Next>':                  self.on_key_move_page_down,
            '<Shift-Next>':            self.on_key_move_page_down,

            '<Home>':                  self.on_key_goto_line_start,
            '<Shift-Home>':            self.on_key_goto_line_start,

            '<End>':                   self.on_key_goto_line_endin,
            '<Shift-End>':             self.on_key_goto_line_endin,

            '<Control-g>':             self.on_key_goto_memory_focus,
            '<Control-G>':             self.on_key_goto_memory_apply,

            '<Control-Home>':          self.on_key_goto_memory_start,
            '<Control-Shift-Home>':    self.on_key_goto_memory_start,

            '<Control-End>':           self.on_key_goto_memory_endin,
            '<Control-Shift-End>':     self.on_key_goto_memory_endin,

            '<Control-Alt-End>':       self.on_key_goto_memory_endex,
            '<Control-Alt-Shift-End>': self.on_key_goto_memory_endex,

            '<Alt-Home>':              self.on_key_goto_block_start,
            '<Alt-Shift-Home>':        self.on_key_goto_block_start,

            '<Alt-End>':               self.on_key_goto_block_endin,
            '<Alt-Shift-End>':         self.on_key_goto_block_endin,

            '<Alt-Insert>':            self.on_key_copy_address,
            '<Alt-Shift-Insert>':      self.on_key_set_address,
            '<Control-a>':             self.on_key_select_all,
            '<Control-r>':             self.on_key_select_range,
            '<Escape>':                self.on_key_escape_selection,
            '<Insert>':                self.on_key_switch_cursor_mode,
            '<F5>':                    self.on_key_redraw,

            '<Control-z>':             self.on_key_undo,
            '<Alt-BackSpace>':         self.on_key_undo,
            '<Control-Z>':             self.on_key_redo,
            '<Control-y>':             self.on_key_redo,
            '<Alt-Shift-BackSpace>':   self.on_key_redo,
        }

        mouse_bindings = {
            '<Button-1>':              self.on_cells_selection_press,
            '<Double-Button-1>':       self.on_cells_selection_double,
            '<Shift-Button-1>':        self.on_cells_selection_motion,
            '<B1-Motion>':             self.on_cells_selection_motion,
            '<ButtonRelease-1>':       self.on_cells_selection_release,
            '<MouseWheel>':            self.on_cells_chars_wheel,
        }

        # Bind data view canvas actions
        cells_canvas = self.cells_canvas

        for key, handler in control_bindings.items():
            cells_canvas.bind(key, handler)

        for key, handler in mouse_bindings.items():
            cells_canvas.bind(key, handler)

        for key in HEX_SET:
            cells_canvas.bind(key, self.on_key_digit_cells)

        cells_canvas.bind('<FocusIn>', self.on_cells_focus_in)
        cells_canvas.bind('<FocusOut>', self.on_cells_focus_out)

        # Bind address canvas actions
        address_canvas = self.address_canvas
        address_canvas.bind('<MouseWheel>', self.on_cells_chars_wheel)

        # Bind chars canvas actions
        control_bindings.update({
            '<Left>':           self.on_key_move_left_byte,
            '<Right>':          self.on_key_move_right_byte,
        })

        mouse_bindings = {
            '<Button-1>':        self.on_chars_selection_press,
            '<Double-Button-1>': self.on_chars_selection_double,
            '<Shift-Button-1>':  self.on_chars_selection_motion,
            '<B1-Motion>':       self.on_chars_selection_motion,
            '<ButtonRelease-1>': self.on_chars_selection_release,
            '<MouseWheel>':      self.on_cells_chars_wheel,
        }

        chars_canvas = self.chars_canvas

        for key, handler in control_bindings.items():
            chars_canvas.bind(key, handler)

        for key, handler in mouse_bindings.items():
            chars_canvas.bind(key, handler)

        chars_canvas.bind('<Key>', self.on_key_digit_chars)
        chars_canvas.bind('<FocusIn>', self.on_chars_focus_in)
        chars_canvas.bind('<FocusOut>', self.on_chars_focus_out)

        # Bind widget actions
        self.bind('<Configure>', self.on_configure)

    def focus_set(self) -> None:
        self.focus_set_cells()

    def focus_set_cells(self) -> None:
        self._cells_canvas.focus_set()

    def focus_set_chars(self) -> None:
        if self._chars_visible:
            self._chars_canvas.focus_set()
        else:
            self.focus_set_cells()

    @property
    def cells_canvas(self) -> tk.Canvas:
        return self._cells_canvas

    @property
    def address_canvas(self) -> tk.Canvas:
        return self._address_canvas

    @property
    def offset_canvas(self) -> tk.Canvas:
        return self._offset_canvas

    @property
    def chars_canvas(self) -> tk.Canvas:
        return self._chars_canvas

    @BaseEditorWidget.chars_visible.setter
    def chars_visible(self, visible: bool) -> None:
        visible = bool(visible)

        if self._chars_visible < visible:
            self._chars_visible = visible
            self._chars_title.grid()
            self._chars_canvas.grid()
            self._chars_hbar.grid()
            self.columnconfigure(3, weight=1, minsize=64)
            self.redraw()

        elif self._chars_visible > visible:
            self._chars_visible = visible
            self._chars_title.grid_remove()
            self._chars_canvas.grid_remove()
            self._chars_hbar.grid_remove()
            self.columnconfigure(3, weight=0, minsize=0)
            self.redraw()

    def get_half_page_height(self) -> CellCoord:
        cell_y = self._cells_canvas.winfo_height() // (self._font_h * 2)
        return cell_y

    def _on_hbar(self, *args):
        self._cells_canvas.xview(*args)
        self._offset_canvas.xview(*args)
        # self._cells_pixel_x = self._cells_canvas.canvasx(0)
        view_ratio_x = self._offset_canvas.xview()[0]
        self._cells_pixel_x = floor(self._cells_pixel_size[0] * view_ratio_x)

    def _on_vbar(self, mode, *args):
        cells_pixel_y = cells_pixel_y_prev = self._cells_pixel_y
        font_w, font_h = self._font_w, self._font_h

        if mode == tk.MOVETO:
            offset, = args

        elif mode == tk.SCROLL:
            step, what = args
            step = int(step)

            if what == tk.UNITS:
                if step > 0:
                    for _ in range(step):
                        remainder = cells_pixel_y % font_h
                        cells_pixel_y += font_h - remainder
                elif step < 0:
                    for _ in range(-step):
                        remainder = cells_pixel_y % font_h
                        cells_pixel_y -= remainder if remainder else font_h

            elif what == tk.PAGES:
                page_h = font_h * 0x100
                if step > 0:
                    for _ in range(step):
                        remainder = cells_pixel_y % page_h
                        cells_pixel_y += page_h - remainder
                elif step < 0:
                    for _ in range(-step):
                        remainder = cells_pixel_y % page_h
                        cells_pixel_y -= remainder if remainder else page_h

        if cells_pixel_y_prev != cells_pixel_y:
            self._cells_pixel_y = cells_pixel_y
            self.update_view()
            self.update_vbar()

    def on_key_digit_cells(self, event=None):
        self.after_idle(self._on_key_digit_cells, event)

    def _on_key_digit_cells(self, event=None):
        digit_char = event.char
        if digit_char.isprintable():
            self._engine.on_key_digit_cells(digit_char)

    def on_key_digit_chars(self, event=None):
        self.after_idle(self._on_key_digit_chars, event)

    def _on_key_digit_chars(self, event=None):
        digit_char = event.char
        if digit_char.isprintable():
            self._engine.on_key_digit_chars(digit_char)

    def on_key_reserve_cell(self, event=None):
        self._engine.on_key_reserve_cell()

    def on_key_delete_cell(self, event=None):
        self._engine.on_key_delete_cell()

    def on_key_clear_cell(self, event=None):
        self._engine.on_key_clear_cell()

    def on_key_clear_back(self, event=None):
        self._engine.on_key_clear_back()

    def on_key_clear_next(self, event=None):
        self._engine.on_key_clear_next()

    def on_key_delete(self, event=None):
        self._engine.on_key_delete()

    def on_key_fill(self, event=None):
        self._engine.on_key_fill()

    def on_key_flood(self, event=None):
        self._engine.on_key_flood()

    def on_key_cut(self, event=None):
        self._engine.on_key_cut()

    def on_key_copy(self, event=None):
        self._engine.on_key_copy()

    def on_key_paste(self, event=None):
        self._engine.on_key_paste()

    def on_key_crop(self, event=None):
        self._engine.on_key_crop()

    def on_key_move_focus(self, event=None):
        self._engine.on_key_move_focus()

    def on_key_move_apply(self, event=None):
        self._engine.on_key_move_apply()

    def on_key_scroll_line_up(self, event=None):
        self._engine.on_key_scroll_line_up()

    def on_key_scroll_page_up(self, event=None):
        self._engine.on_key_scroll_page_up()

    def on_key_scroll_line_down(self, event=None):
        self._engine.on_key_scroll_line_down()

    def on_key_scroll_page_down(self, event=None):
        self._engine.on_key_scroll_page_down()

    def on_key_scroll_top(self, event=None):
        self._engine.on_key_scroll_top()

    def on_key_scroll_bottom(self, event=None):
        self._engine.on_key_scroll_bottom()

    def on_key_move_left_digit(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_move_left_digit(shift)

    def on_key_move_right_digit(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_move_right_digit(shift)

    def on_key_move_left_byte(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_move_left_byte(shift)

    def on_key_move_right_byte(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_move_right_byte(shift)

    def on_key_move_line_up(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_move_line_up(shift)

    def on_key_move_page_up(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_move_page_up(shift)

    def on_key_move_line_down(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_move_line_down(shift)

    def on_key_move_page_down(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_move_page_down(shift)

    def on_key_goto_line_start(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_goto_line_start(shift)

    def on_key_goto_line_endin(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_goto_line_endin(shift)

    def on_key_goto_memory_apply(self, event=None):
        self._engine.on_key_goto_memory_apply()

    def on_key_goto_memory_focus(self, event=None):
        self._engine.on_key_goto_memory_focus()

    def on_key_goto_memory_start(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_goto_memory_start(shift)

    def on_key_goto_memory_endin(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_goto_memory_endin(shift)

    def on_key_goto_memory_endex(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_goto_memory_endex(shift)

    def on_key_goto_block_previous(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_goto_block_previous(shift)

    def on_key_goto_block_next(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_goto_block_next(shift)

    def on_key_goto_block_start(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_goto_block_start(shift)

    def on_key_goto_block_endin(self, event=None):
        shift = _is_shift_in_event(event)
        self._engine.on_key_goto_block_endin(shift)

    def on_key_copy_address(self, event=None):
        self._engine.on_key_copy_address()

    def on_key_set_address(self, event=None):
        self._engine.on_key_set_address()

    def on_key_select_all(self, event=None):
        self._engine.on_key_select_all()

    def on_key_select_range(self, event=None):
        self._engine.on_key_select_range()

    def on_key_escape_selection(self, event=None):
        self._engine.on_key_escape_selection()

    def on_key_switch_cursor_mode(self, event=None):
        self._engine.on_key_switch_cursor_mode()

    def on_key_redraw(self, event=None):
        self._engine.on_key_redraw()

    def on_key_undo(self, event=None):
        self._engine.on_key_undo()

    def on_key_redo(self, event=None):
        self._engine.on_key_redo()

    def on_cells_selection_press(self, event=None):
        cell_x, cell_y, digit = self.event_to_cursor_coords(event)
        self._engine.on_cells_selection_press(cell_x, cell_y, digit)

    def on_cells_selection_double(self, event=None):
        cell_x, cell_y, digit = self.event_to_cursor_coords(event)
        self._engine.on_cells_selection_double(cell_x, cell_y, digit)

    def on_cells_selection_motion(self, event=None):
        cell_x, cell_y, digit = self.event_to_cursor_coords(event)
        self._engine.on_cells_selection_motion(cell_x, cell_y, digit)

    def on_cells_selection_release(self, event=None):
        cell_x, cell_y, digit = self.event_to_cursor_coords(event)
        self._engine.on_cells_selection_release(cell_x, cell_y, digit)

    def on_chars_selection_press(self, event=None):
        char_x, char_y = self.event_to_char_coords(event)
        self._engine.on_chars_selection_press(char_x, char_y)

    def on_chars_selection_double(self, event=None):
        char_x, char_y = self.event_to_char_coords(event)
        self._engine.on_chars_selection_double(char_x, char_y)

    def on_chars_selection_motion(self, event=None):
        char_x, char_y = self.event_to_char_coords(event)
        self._engine.on_chars_selection_motion(char_x, char_y)

    def on_chars_selection_release(self, event=None):
        char_x, char_y = self.event_to_char_coords(event)
        self._engine.on_chars_selection_release(char_x, char_y)

    def on_cells_chars_wheel(self, event=None):
        self.scroll_wheel(event)

    def on_configure(self, event=None):
        self.update_idletasks()

        view_ratio_x = self._offset_canvas.xview()[0]
        self._cells_pixel_x = floor(self._cells_pixel_size[0] * view_ratio_x)

        self.update_vbar()
        self.update_view()

    def on_cells_focus_in(self, event=None):
        self._cells_cursor_color = _COLOR_CUR
        self.update_cursor()

    def on_cells_focus_out(self, event=None):
        self._cells_cursor_color = _COLOR_FG
        self.update_cursor()

    def on_chars_focus_in(self, event=None):
        self._chars_cursor_color = _COLOR_CUR
        self.update_cursor()

    def on_chars_focus_out(self, event=None):
        self._chars_cursor_color = _COLOR_FG
        self.update_cursor()

    def _on_wheel(self, event=None):
        step = -int(event.delta) // self._font_h
        self._on_vbar(tk.SCROLL, step, tk.UNITS)

    def get_cell_bounds_y(self) -> Tuple[CellCoord, CellCoord]:
        pad_y = self._pad_y
        pixel_h = self.cells_canvas.winfo_height()
        cell_start_y = floor(self.pixel_to_cell_coords(0, pad_y)[1])
        cell_endex_y = floor(self.pixel_to_cell_coords(0, pixel_h - pad_y)[1])
        return cell_start_y, cell_endex_y

    def mark_dirty_cell(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
    ):
        self._cells_dirty.add((cell_x, cell_y))

    def mark_dirty_all(self):
        self._cells_dirty.update(self._cells_text_id.keys())

    def mark_dirty_inline(
        self,
        start_x: Optional[CellCoord] = None,
        start_y: Optional[CellCoord] = None,
        endin_x: Optional[CellCoord] = None,
        endin_y: Optional[CellCoord] = None,
    ):
        if start_y is None:
            start_y = self._cell_start[1]
        if endin_y is None:
            endin_y = self._cell_endex[1] - 1

        if start_y <= endin_y:
            if start_x is None:
                start_x = self._cell_start[0]
            if endin_x is None:
                endin_x = self._cell_endex[0] - 1

            status = self._status
            line_length = status.line_length
            cells_dirty = self._cells_dirty

            if start_y == endin_y:
                cells_dirty.update((x, start_y) for x in range(start_x, endin_x + 1))
            else:
                cells_dirty.update((x, start_y) for x in range(start_x, line_length))
                cells_dirty.update((x, y) for y in range(start_y + 1, endin_y) for x in range(0, line_length))
                cells_dirty.update((x, endin_y) for x in range(0, endin_x + 1))

    def mark_dirty_range(
        self,
        start_address: Optional[Address] = None,
        endex_address: Optional[Address] = None,
    ):
        status = self._status

        if start_address is None:
            start_x, start_y = None, None
        else:
            start_x, start_y = status.address_to_cell_coords(start_address)

        if endex_address is None:
            endin_x, endin_y = None, None
        else:
            endin_x, endin_y = status.address_to_cell_coords(max(start_address, endex_address - 1))

        self.mark_dirty_inline(start_x, start_y, endin_x, endin_y)

    def update_vbar(self):
        status = self._status
        memory = status.memory

        memory_start = memory.start
        memory_endex = memory.endex
        memory_start_y = status.address_to_cell_coords(memory_start)[1]
        memory_endex_y = status.address_to_cell_coords(max(memory_start, memory_endex - 1))[1] + 1

        pixel_w, pixel_h = (self._cells_pixel_size[0], self._cells_canvas.winfo_height())
        cell_start_y = self.pixel_to_cell_coords(0, 0)[1]
        cell_endin_y = self.pixel_to_cell_coords(pixel_w - 1, pixel_h - 1)[1]

        ratio_start = (cell_start_y - memory_start_y) / (memory_endex_y - memory_start_y)
        ratio_endin = (cell_endin_y - memory_start_y) / (memory_endex_y - memory_start_y)
        vbar_start = max(0., min(ratio_start, 1.))
        vbar_endin = max(0., min(ratio_endin, 1.))

        self._cells_vbar.set(vbar_start, vbar_endin)

    def update_view(
        self,
        force_geometry: bool = False,
        force_selection: bool = False,
        force_content: bool = False,
    ):
        status = self._status
        cells_canvas = self._cells_canvas

        # Resize canvas if required
        pad_x, pad_y = self._pad_x, self._pad_y
        font_w, font_h = self._font_w, self._font_h
        cell_format_length = status.cell_format_length
        line_length = status.line_length
        view_w = pad_x + (font_w * (line_length * (cell_format_length + status.cell_spacing) - 1)) + pad_x
        pixel_w = self._cells_pixel_size[0]
        if view_w != pixel_w:
            pixel_w, pixel_h = view_w, cells_canvas.winfo_height()
            cells_pixel_size = pixel_w, pixel_h
            cells_canvas.configure(width=pixel_w, height=pixel_h)
        else:
            cells_pixel_size = (pixel_w, cells_canvas.winfo_height())
            pixel_w, pixel_h = cells_pixel_size

        cell_start_x, cell_start_y = self.pixel_to_cell_coords(0, 0)
        cell_start_x, cell_start_y = max(0, floor(cell_start_x)), floor(cell_start_y)
        cell_endex_x, cell_endex_y = self.pixel_to_cell_coords(pixel_w, pixel_h)
        cell_endex_x, cell_endex_y = min(floor(cell_endex_x) + 1, line_length), floor(cell_endex_y) + 1
        self._cell_start = (cell_start_x, cell_start_y)
        self._cell_endex = (cell_endex_x, cell_endex_y)
        self._address_start = status.cell_coords_to_address(cell_start_x, cell_start_y)
        self._address_endex = status.cell_coords_to_address(cell_endex_x, cell_endex_y)

        changed_geometry = (force_geometry or
                            self._cells_pixel_size != cells_pixel_size or
                            self._cells_pixel_y_prev != self._cells_pixel_y)

        changed_selection = (force_selection or
                             self._sel_start_address_prev != status.sel_start_address or
                             self._sel_endin_address_prev != status.sel_endin_address)

        changed_content = force_content

        if changed_geometry:
            self._update_geometry()

        if changed_geometry or changed_content:
            self._update_content()

        if changed_geometry or changed_selection:
            self._update_background()

        self._cells_dirty.clear()
        self.update_cursor()

        self._cells_pixel_size = cells_pixel_size
        self._cells_pixel_y_prev = self._cells_pixel_y
        self._sel_start_address_prev = status.sel_start_address
        self._sel_endin_address_prev = status.sel_endin_address

    def _update_geometry(self):
        status = self._status
        cell_start_x, cell_start_y = self._cell_start
        cell_endex_x, cell_endex_y = self._cell_endex

        address_canvas = self._address_canvas
        chars_canvas = self._chars_canvas
        cells_canvas = self._cells_canvas
        line_length = status.line_length

        addrs_text_id = self._addrs_text_id
        cells_text_id = self._cells_text_id
        cells_rect_id = self._cells_rect_id
        chars_text_id = self._chars_text_id
        chars_rect_id = self._chars_rect_id

        cells_key_keep = set()
        cells_key_miss = set()
        addrs_key_keep = set()
        addrs_key_miss = set()

        # Mark missing cells and addresses, and those to be kept
        for y in range(cell_start_y, cell_endex_y):
            for x in range(cell_start_x, cell_endex_x):
                x_y = (x, y)
                if x_y in cells_text_id:
                    cells_key_keep.add(x_y)
                else:
                    cells_key_miss.add(x_y)
            if y in addrs_text_id:
                addrs_key_keep.add(y)
            else:
                addrs_key_miss.add(y)

        cells_key_trash = [x_y for x_y in cells_text_id if x_y not in cells_key_keep]
        addrs_key_trash = [y for y in addrs_text_id if y not in addrs_key_keep]

        font_w, font_h = self._font_w, self._font_h
        pad_x, pad_y = self._pad_x, self._pad_y

        # Update address skip
        address_format = status.address_format_string
        address_skip = status.address_skip
        text = address_format.format(address_skip)
        self._address_skip_label.configure(text=text)

        # Instance missing addresses
        for y in addrs_key_miss:
            address = status.cell_coords_to_address(0, y)
            text = address_format.format(address)
            addr_pixel_x = pad_x
            addr_pixel_y = pad_y + (y * font_h) - self._cells_pixel_y
            if addrs_key_trash:
                addr_text_id = addrs_text_id.pop(addrs_key_trash.pop())
                address_canvas.coords(addr_text_id, addr_pixel_x, addr_pixel_y)
                address_canvas.itemconfigure(addr_text_id, text=text)
            else:
                addr_text_id = address_canvas.create_text(addr_pixel_x, addr_pixel_y, text=text, anchor=tk.NW,
                                                          font=self._font, fill=_COLOR_FG)
            addrs_text_id[y] = addr_text_id

        # Remove trashed addresses
        for y in addrs_key_trash:
            address_canvas.delete(addrs_text_id.pop(y))

        # Update kept addresses
        for y in addrs_key_keep:
            addr_pixel_x = pad_x
            addr_pixel_y = pad_y + (y * font_h) - self._cells_pixel_y
            address_canvas.coords(addrs_text_id[y], addr_pixel_x, addr_pixel_y)

        # Instance missing cells
        cells_dirty = self._cells_dirty
        cells_pixel = self._cells_pixel
        cells_selected = self._cells_selected
        cells_text = self._cells_text_str
        font = self._font
        cell_format_length = status.cell_format_length
        rect_w_tail = cell_format_length * font_w
        rect_w_body = rect_w_tail + (font_w * status.cell_spacing)
        rect_h = font_h
        cell_x_endin = line_length - 1
        cell_text = '?' * status.cell_format_length
        char_text = '?'
        chars_visible = self._chars_visible
        char_text_id = None
        char_rect_id = None

        for x_y in cells_key_miss:
            cell_pixel_x, cell_pixel_y = self.cell_coords_to_pixel(*x_y)
            char_pixel_x, char_pixel_y = self.char_coords_to_pixel(*x_y)
            rect_w = rect_w_body if x_y[0] < cell_x_endin else rect_w_tail

            if cells_key_trash:
                key = cells_key_trash.pop()

                cell_text_id = cells_text_id.pop(key)
                cells_canvas.coords(cell_text_id, cell_pixel_x, cell_pixel_y)
                cells_canvas.itemconfigure(cell_text_id, text=cell_text)

                cell_rect_id = cells_rect_id.pop(key)
                cells_canvas.itemconfigure(cell_rect_id, state=tk.HIDDEN)
                cells_canvas.coords(cell_rect_id,
                                    cell_pixel_x, cell_pixel_y,
                                    cell_pixel_x + rect_w, cell_pixel_y + rect_h)

                if chars_visible:
                    char_text_id = chars_text_id.pop(key)
                    chars_canvas.coords(char_text_id, char_pixel_x, char_pixel_y)
                    chars_canvas.itemconfigure(char_text_id, text=char_text)

                    char_rect_id = chars_rect_id.pop(key)
                    chars_canvas.itemconfigure(char_rect_id, state=tk.HIDDEN)
                    chars_canvas.coords(char_rect_id,
                                        char_pixel_x, char_pixel_y,
                                        char_pixel_x + font_w, char_pixel_y + rect_h)

            else:
                cell_text_id = cells_canvas.create_text(cell_pixel_x, cell_pixel_y,
                                                        tags='cell_text', text=cell_text,
                                                        anchor=tk.NW, font=font, fill=_COLOR_FG)

                cell_rect_id = cells_canvas.create_rectangle(cell_pixel_x, cell_pixel_y,
                                                             cell_pixel_x + rect_w, cell_pixel_y + rect_h,
                                                             tags='cell_rect', outline='', fill=_COLOR_SEL_BG,
                                                             state=tk.HIDDEN)

                if chars_visible:
                    char_text_id = chars_canvas.create_text(char_pixel_x, char_pixel_y,
                                                            tags='char_text', text=char_text,
                                                            anchor=tk.NW, font=font, fill=_COLOR_FG)

                    char_rect_id = chars_canvas.create_rectangle(char_pixel_x, char_pixel_y,
                                                                 char_pixel_x + font_w, char_pixel_y + font_h,
                                                                 tags='char_rect', outline='', fill=_COLOR_SEL_BG,
                                                                 state=tk.HIDDEN)

            cells_text_id[x_y] = cell_text_id
            cells_rect_id[x_y] = cell_rect_id
            if chars_visible:
                chars_text_id[x_y] = char_text_id
                chars_rect_id[x_y] = char_rect_id

            cells_dirty.add(x_y)
            cells_pixel[x_y] = (-1, -1)  # invalidate
            cells_selected.add(x_y)
            cells_text[x_y] = ''  # invalidate

        cells_canvas.tag_raise('cell_text')
        cells_canvas.tag_lower('cell_rect')
        if chars_visible:
            chars_canvas.tag_raise('char_text')
            chars_canvas.tag_lower('char_rect')

        # Remove trashed cells
        for x_y in cells_key_trash:
            cells_canvas.delete(cells_text_id.pop(x_y))
            cells_canvas.delete(cells_rect_id.pop(x_y))
            if chars_visible:
                chars_canvas.delete(chars_text_id.pop(x_y))
                chars_canvas.delete(chars_rect_id.pop(x_y))
            cells_dirty.discard(x_y)
            cells_pixel.pop(x_y)
            cells_selected.discard(x_y)
            cells_text.pop(x_y)

        # Update kept cells
        for x_y in cells_key_keep:
            cell_pixel = self.cell_coords_to_pixel(*x_y)
            char_pixel = self.char_coords_to_pixel(*x_y)

            if cells_pixel[x_y] != cell_pixel:
                cells_pixel[x_y] = cell_pixel
                cell_pixel_x, cell_pixel_y = cell_pixel
                char_pixel_x, char_pixel_y = char_pixel

                cells_canvas.coords(cells_text_id[x_y], cell_pixel_x, cell_pixel_y)

                rect_w = rect_w_body if x_y[0] < cell_x_endin else rect_w_tail
                cells_canvas.coords(cells_rect_id[x_y],
                                    cell_pixel_x, cell_pixel_y,
                                    cell_pixel_x + rect_w, cell_pixel_y + rect_h)

                if chars_visible:
                    chars_canvas.coords(chars_text_id[x_y], char_pixel_x, char_pixel_y)

                    chars_canvas.coords(chars_rect_id[x_y],
                                        char_pixel_x, char_pixel_y,
                                        char_pixel_x + font_w, char_pixel_y + font_h)

        # Update canvas sizes
        offset_canvas = self._offset_canvas
        offset_spacing = status.offset_spacing
        offset_format_format = status.offset_format_string.format
        offset_format_spacing = ' ' * offset_spacing
        text = offset_format_spacing.join(offset_format_format(x) for x in range(line_length))
        text = offset_format_spacing[:-1] + text
        offset_canvas.itemconfigure(self._offset_text_id, text=text)

        offset_format_length = status.offset_format_length
        offset_canvas_w = pad_x + (font_w * (line_length * (offset_format_length + offset_spacing) - 1)) + pad_x
        view_w = pad_x + (font_w * (line_length * (cell_format_length + status.cell_spacing) - 1)) + pad_x
        view_w = offset_canvas_w = max(offset_canvas_w, view_w)
        offset_canvas.configure(width=offset_canvas_w, scrollregion=(0, 0, offset_canvas_w, 1))
        cells_canvas.configure(width=view_w, scrollregion=(0, 0, view_w, 1))

        chars_canvas_w = pad_x + (font_w * line_length) + pad_x
        chars_canvas.configure(width=chars_canvas_w, scrollregion=(0, 0, chars_canvas_w, 1))

        address_format_length = status.address_format_length
        address_canvas_w = pad_x + (font_w * address_format_length) + pad_x
        address_canvas.configure(width=address_canvas_w)

    def _update_content(self):
        status = self._status
        cell_start_x, cell_start_y = self._cell_start
        cell_endex_x, cell_endex_y = self._cell_endex

        cells_canvas = self._cells_canvas
        chars_canvas = self._chars_canvas
        chars_title = self._chars_title

        cells_text_id = self._cells_text_id
        cells_dirty = self._cells_dirty
        cells_text_str = self._cells_text_str
        chars_text_id = self._chars_text_id

        address = status.cell_coords_to_address(cell_start_x, cell_start_y)
        rover = status.memory.values(address, ...).__next__
        text_format = status.cell_format_string.format
        text_empty = '-' * status.cell_format_length
        char_empty = ' '
        chars_visible = self._chars_visible
        chars_table = status.chars_table

        chars_title.configure(text=f'Text / {status.chars_encoding}')

        for y in range(cell_start_y, cell_endex_y):
            for x in range(cell_start_x, cell_endex_x):
                value = rover()
                x_y = (x, y)

                if x_y in cells_dirty:
                    text_before = cells_text_str[x_y]
                    text_after = text_empty if value is None else text_format(value)

                    if text_before != text_after:
                        cells_text_str[x_y] = text_after
                        cells_canvas.itemconfigure(cells_text_id[x_y], text=text_after)

                        if chars_visible:
                            c = char_empty if value is None else chars_table[value]
                            chars_canvas.itemconfigure(chars_text_id[x_y], text=c)

                address += 1

    def _update_background(self):
        status = self._status
        cell_start_x, cell_start_y = self._cell_start
        cell_endex_x, cell_endex_y = self._cell_endex

        selection_mode = status.sel_mode
        sm_norm = SelectionMode.NORMAL
        sm_rect = SelectionMode.RECTANGLE
        sel_address_start = status.sel_start_address
        sel_address_endin = status.sel_endin_address
        sel_start_cell_x, sel_start_cell_y = status.sel_start_cell
        sel_endin_cell_x, sel_endin_cell_y = status.sel_endin_cell

        cells_canvas = self._cells_canvas
        chars_canvas = self._chars_canvas

        cells_dirty = self._cells_dirty
        cells_selected_before = self._cells_selected
        cells_selected_after = set()

        if selection_mode == sm_norm:
            # Straighten any backwards selections
            if sel_address_endin < sel_address_start:
                sel_address_endin, sel_address_start = sel_address_start, sel_address_endin

            # Mark those cells within the selected address range
            address = status.cell_coords_to_address(cell_start_x, cell_start_y)
            for y in range(cell_start_y, cell_endex_y):
                for x in range(cell_start_x, cell_endex_x):
                    if sel_address_start <= address <= sel_address_endin:
                        cells_selected_after.add((x, y))
                    address += 1

        elif selection_mode == sm_rect:
            # Straighten any backwards selections
            if sel_endin_cell_x < sel_start_cell_x:
                sel_endin_cell_x, sel_start_cell_x = sel_start_cell_x, sel_endin_cell_x
            if sel_endin_cell_y < sel_start_cell_y:
                sel_endin_cell_y, sel_start_cell_y = sel_start_cell_y, sel_endin_cell_y

            # Mark those cells within the selected rectangle range
            for y in range(cell_start_y, cell_endex_y):
                for x in range(cell_start_x, cell_endex_x):
                    if ((sel_start_cell_x <= x <= sel_endin_cell_x and
                         sel_start_cell_y <= y <= sel_endin_cell_y)):
                        cells_selected_after.add((x, y))

        # Update only those cells that changed selection state
        cells_text_id = self._cells_text_id
        cells_rect_id = self._cells_rect_id
        chars_text_id = self._chars_text_id
        chars_rect_id = self._chars_rect_id
        chars_visible = self._chars_visible
        palette = (_COLOR_FG, _COLOR_OG)
        palette_sel = (_COLOR_SEL_FG, _COLOR_SEL_OG)

        for y in range(cell_start_y, cell_endex_y):
            for x in range(cell_start_x, cell_endex_x):
                x_y = (x, y)
                selected_after = x_y in cells_selected_after

                if x_y in cells_dirty:
                    selected_before = not selected_after  # force update
                else:
                    selected_before = x_y in cells_selected_before

                if selected_before < selected_after:
                    color = palette_sel[x & 1]
                    cells_canvas.itemconfigure(cells_text_id[x_y], fill=color)
                    cells_canvas.itemconfigure(cells_rect_id[x_y], state=tk.NORMAL)
                    if chars_visible:
                        chars_canvas.itemconfigure(chars_text_id[x_y], fill=color)
                        chars_canvas.itemconfigure(chars_rect_id[x_y], state=tk.NORMAL)

                elif selected_before > selected_after:
                    color = palette[x & 1]
                    cells_canvas.itemconfigure(cells_text_id[x_y], fill=color)
                    cells_canvas.itemconfigure(cells_rect_id[x_y], state=tk.HIDDEN)
                    if chars_visible:
                        chars_canvas.itemconfigure(chars_text_id[x_y], fill=color)
                        chars_canvas.itemconfigure(chars_rect_id[x_y], state=tk.HIDDEN)

        self._cells_selected = cells_selected_after

    def update_cursor(self):
        status = self._status
        cell_start_x, cell_start_y = self._cell_start
        cell_endex_x, cell_endex_y = self._cell_endex
        cursor_cell_x, cursor_cell_y = status.cursor_cell
        cells_canvas = self._cells_canvas
        chars_canvas = self._chars_canvas
        chars_visible = self._chars_visible

        if ((cell_start_x <= cursor_cell_x <= cell_endex_x and
             cell_start_y <= cursor_cell_y <= cell_endex_y)):

            cursor_pixel_x, cursor_pixel_y = self.cell_coords_to_pixel(cursor_cell_x, cursor_cell_y)
            font_w, font_h = self._font_w, self._font_h
            cursor_pixel_x += status.cursor_digit * font_w
            cells_canvas.itemconfigure(self._cells_cursor_id, fill=self._cells_cursor_color)
            chars_canvas.itemconfigure(self._chars_cursor_id, fill=self._chars_cursor_color)

            if status.cursor_mode == CursorMode.OVERWRITE:
                # Draw a box around the cursor character
                cells_canvas.coords(self._cells_cursor_id,
                                    cursor_pixel_x - 1, cursor_pixel_y - 1,
                                    cursor_pixel_x - 1, cursor_pixel_y + font_h + 1,
                                    cursor_pixel_x + font_w + 1, cursor_pixel_y + font_h + 1,
                                    cursor_pixel_x + font_w + 1, cursor_pixel_y - 1,
                                    cursor_pixel_x - 1, cursor_pixel_y - 1)

                if chars_visible:
                    cursor_pixel_x, cursor_pixel_y = self.char_coords_to_pixel(cursor_cell_x, cursor_cell_y)
                    chars_canvas.coords(self._chars_cursor_id,
                                        cursor_pixel_x - 1, cursor_pixel_y - 1,
                                        cursor_pixel_x - 1, cursor_pixel_y + font_h + 1,
                                        cursor_pixel_x + font_w + 1, cursor_pixel_y + font_h + 1,
                                        cursor_pixel_x + font_w + 1, cursor_pixel_y - 1,
                                        cursor_pixel_x - 1, cursor_pixel_y - 1)

            else:
                # Draw a vertical line on the left side of the cursor character
                cells_canvas.coords(self._cells_cursor_id,
                                    cursor_pixel_x - 1, cursor_pixel_y - 1,
                                    cursor_pixel_x - 1, cursor_pixel_y + font_h + 1)

                if chars_visible:
                    cursor_pixel_x, cursor_pixel_y = self.char_coords_to_pixel(cursor_cell_x, cursor_cell_y)
                    chars_canvas.coords(self._chars_cursor_id,
                                        cursor_pixel_x - 1, cursor_pixel_y - 1,
                                        cursor_pixel_x - 1, cursor_pixel_y + font_h + 1)

            cells_canvas.tag_raise('cursor')
            chars_canvas.tag_raise('cursor')

        else:
            # Park to an invisible spot
            cells_canvas.coords(self._cells_cursor_id, -2, -2, -1, -1)
            if chars_visible:
                chars_canvas.coords(self._chars_cursor_id, -2, -2, -1, -1)

    def redraw(self):
        for cell_text_id in self._cells_text_id.values():
            self._cells_canvas.delete(cell_text_id)

        for cell_rect_id in self._cells_rect_id.values():
            self._cells_canvas.delete(cell_rect_id)

        for char_text_id in self._chars_text_id.values():
            self._chars_canvas.delete(char_text_id)

        for char_rect_id in self._chars_rect_id.values():
            self._chars_canvas.delete(char_rect_id)

        for addr_text_id in self._addrs_text_id.values():
            self._address_canvas.delete(addr_text_id)

        self._addrs_text_id.clear()
        self._cells_text_id.clear()
        self._cells_rect_id.clear()
        self._cells_dirty.clear()
        self._cells_pixel.clear()
        self._cells_selected.clear()
        self._cells_text_str.clear()
        self._chars_text_id.clear()
        self._chars_rect_id.clear()

        self.update_view(force_geometry=True, force_selection=True, force_content=True)
        self.update_vbar()

    def pixel_to_char_coords(self, pixel_x: PixelCoord, pixel_y: PixelCoord) -> FloatCoords:
        char_x = (pixel_x - self._pad_x) / self._font_w
        char_y = (pixel_y - self._pad_y + self._cells_pixel_y) / self._font_h
        return char_x, char_y

    def char_coords_to_pixel(self, char_x: CharCoord, char_y: CharCoord) -> PixelCoords:
        pixel_x = self._pad_x + (char_x * self._font_w)
        pixel_y = self._pad_y + (char_y * self._font_h) - self._cells_pixel_y
        return pixel_x, pixel_y

    def pixel_to_cell_coords(self, pixel_x: PixelCoord, pixel_y: PixelCoord) -> FloatCoords:
        status = self._status
        char_x, char_y = self.pixel_to_char_coords(pixel_x, pixel_y)
        cell_format_length = status.cell_format_length
        cell_spacing = status.cell_spacing
        cell_x = (char_x - (cell_spacing - 1)) / (cell_format_length + cell_spacing)
        cell_y = char_y
        return cell_x, cell_y

    def cell_coords_to_pixel(self, cell_x: CellCoord, cell_y: CellCoord) -> PixelCoords:
        status = self._status
        cell_format_length = status.cell_format_length
        cell_spacing = status.cell_spacing
        char_x = cell_x * (cell_format_length + cell_spacing) + (cell_spacing - 1)
        char_y = cell_y
        return self.char_coords_to_pixel(char_x, char_y)

    def pixel_to_cursor_coords(self, pixel_x: PixelCoord, pixel_y: PixelCoord) -> Tuple[CellCoord, CellCoord, int]:
        status = self._status
        char_x, char_y = self.pixel_to_char_coords(pixel_x, pixel_y)
        cell_format_length = status.cell_format_length
        cell_spacing = status.cell_spacing
        line_length = status.line_length

        cell_format_length_spaced = cell_format_length + cell_spacing
        digit_x_unspaced = char_x - (cell_spacing - 1)
        remainder = digit_x_unspaced % cell_format_length_spaced
        cell_x = floor(digit_x_unspaced / cell_format_length_spaced)
        cell_y = floor(char_y)

        if cell_x < 0:
            cell_x = 0
            digit = 0
        elif cell_x >= line_length:
            cell_x = line_length - 1
            digit = cell_format_length - 1
        else:
            if remainder < 1:
                digit = 0
            elif remainder < cell_format_length + .5:
                digit = min(floor(remainder), cell_format_length - 1)
            elif cell_x < line_length - 1:
                cell_x += 1
                digit = 0
            else:
                digit = cell_format_length - 1

        return cell_x, cell_y, digit

    def event_to_cursor_coords(self, event) -> Tuple[CellCoord, CellCoord, int]:
        return self.pixel_to_cursor_coords(event.x + self._cells_pixel_x, event.y)

    def event_to_char_coords(self, event) -> CharCoords:
        chars_pixel_x = self._chars_canvas.canvasx(0)
        char_x, char_y = self.pixel_to_char_coords(event.x + chars_pixel_x, event.y)
        char_x = max(0, min(floor(char_x), self._status.line_length - 1))
        char_y = floor(char_y)
        return char_x, char_y

    def scroll_up(self, delta_y: int = 1) -> None:
        self._on_vbar(tk.SCROLL, -delta_y, tk.UNITS)

    def scroll_down(self, delta_y: int = 1) -> None:
        self._on_vbar(tk.SCROLL, +delta_y, tk.UNITS)

    def scroll_page_up(self) -> None:
        self.scroll_up(self.get_half_page_height())

    def scroll_page_down(self) -> None:
        self.scroll_down(self.get_half_page_height())

    def scroll_top(self, delta_y: CellCoord = 0) -> None:
        status = self._status
        cursor_cell_y = status.cursor_cell[1] - delta_y
        font_h = self._font_h
        cells_pixel_y = cursor_cell_y * font_h
        changed = (self._cells_pixel_y != cells_pixel_y)
        self._cells_pixel_y = cells_pixel_y
        self.update_view(force_geometry=changed)

    def scroll_bottom(self, delta_y: CellCoord = 0) -> None:
        status = self._status
        cursor_cell_y = status.cursor_cell[1] + delta_y
        font_h = self._font_h
        pad_y = self._pad_y
        pixel_h = self._cells_canvas.winfo_height() - (pad_y * 2)
        cells_pixel_y = ((cursor_cell_y + 1 - (pixel_h // font_h)) * font_h) - (pixel_h % font_h) + pad_y
        changed = (self._cells_pixel_y != cells_pixel_y)
        self._cells_pixel_y = cells_pixel_y
        self.update_view(force_geometry=changed)

    def scroll_wheel(self, event=None):
        step = -int(event.delta) // self._font_h
        self._on_vbar(tk.SCROLL, step, tk.UNITS)

    def ask_big_selection(self, size: Address) -> bool:
        answer = tk.messagebox.askquestion(
            'Big selection',
            (f'{size} ({size:X}h) byes are selected.\n'
             f'Such a big size could create problems.\n'
             f'Continue?')
        )
        return answer == tk.YES


# =====================================================================================================================

class UserInterface(BaseUserInterface):

    def __init__(
        self,
        manager: 'InstanceManager',
        engine_factory: Callable[..., BaseEngine],
    ) -> None:

        super().__init__(manager)
        self._root = manager.root

        self._engine_factory = engine_factory
        engine = engine_factory(self)
        self.engine = engine

        self.__init_top()
        self.__init_tkvars()
        self.__init_menus()
        self.__init_toolbars()
        self.__init_statusbar()
        self.__init_editor()

        self.update_title_by_file_path()
        self.update_menus_by_selection()

        self.top.deiconify()

    def quit(self):
        self.top.destroy()
        super().quit()

    def create_new(self) -> 'UserInterface':
        manager = _cast(InstanceManager, self._manager)
        ui = UserInterface(manager, self._engine_factory)
        return ui

    def __init_top(self):
        top = tk.Toplevel(self._root)
        self.top = top

        top.withdraw()
        top.protocol('WM_DELETE_WINDOW', self._on_delete_window)
        top.title(PROGRAM_TITLE)
        top.minsize(600, 400)

    def _on_delete_window(self):
        self.engine.on_file_exit()

    def __init_tkvars(self):
        # Editor variables
        status = self.engine.status
        top = self.top

        self.line_length_tkvar = tk.IntVar(top, name='line_length', value=status.line_length)
        self.chars_visible_tkvar = tk.BooleanVar(top, name='chars_visible', value=True)
        self.chars_encoding_tkvar = tk.StringVar(top, name='chars_encoding', value='ascii')

        self.cell_mode_tkvar = tk.IntVar(top, name='cell_mode', value=int(status.cell_format_mode))
        self.cell_prefix_tkvar = tk.BooleanVar(top, name='cell_prefix', value=status.cell_format_prefix)
        self.cell_suffix_tkvar = tk.BooleanVar(top, name='cell_suffix', value=status.cell_format_suffix)
        self.cell_zeroed_tkvar = tk.BooleanVar(top, name='cell_zeroed', value=status.cell_format_zeroed)

        self.address_mode_tkvar = tk.IntVar(top, name='address_mode', value=int(status.address_format_mode))
        self.address_prefix_tkvar = tk.BooleanVar(top, name='address_prefix', value=status.address_format_prefix)
        self.address_suffix_tkvar = tk.BooleanVar(top, name='address_suffix', value=status.address_format_suffix)
        self.address_zeroed_tkvar = tk.BooleanVar(top, name='address_zeroed', value=status.address_format_zeroed)
        self.address_skip_tkvar = tk.IntVar(top, name='address_skip', value=status.address_skip)
        self.address_bits_tkvar = tk.IntVar(top, name='address_bits', value=status.address_bits)

        self.offset_mode_tkvar = tk.IntVar(top, name='offset_mode', value=int(status.offset_format_mode))
        self.offset_prefix_tkvar = tk.BooleanVar(top, name='offset_prefix', value=status.offset_format_prefix)
        self.offset_suffix_tkvar = tk.BooleanVar(top, name='offset_suffix', value=status.offset_format_suffix)
        self.offset_zeroed_tkvar = tk.BooleanVar(top, name='offset_zeroed', value=status.offset_format_zeroed)

        # Add variable tracing
        self.line_length_tkvar.trace_add('write', self.on_tkvar_line_length)
        self.chars_visible_tkvar.trace_add('write', self.on_tkvar_chars_visible)
        self.chars_encoding_tkvar.trace_add('write', self.on_tkvar_chars_encoding)

        self.cell_mode_tkvar.trace_add('write', self.on_tkvar_cell_mode)
        self.cell_prefix_tkvar.trace_add('write', self.on_tkvar_cell_prefix)
        self.cell_suffix_tkvar.trace_add('write', self.on_tkvar_cell_suffix)
        self.cell_zeroed_tkvar.trace_add('write', self.on_tkvar_cell_zeroed)

        self.address_mode_tkvar.trace_add('write', self.on_tkvar_address_mode)
        self.address_prefix_tkvar.trace_add('write', self.on_tkvar_address_prefix)
        self.address_suffix_tkvar.trace_add('write', self.on_tkvar_address_suffix)
        self.address_zeroed_tkvar.trace_add('write', self.on_tkvar_address_zeroed)
        self.address_skip_tkvar.trace_add('write', self.on_tkvar_address_skip)
        self.address_bits_tkvar.trace_add('write', self.on_tkvar_address_bits)

        self.offset_mode_tkvar.trace_add('write', self.on_tkvar_offset_mode)
        self.offset_prefix_tkvar.trace_add('write', self.on_tkvar_offset_prefix)
        self.offset_suffix_tkvar.trace_add('write', self.on_tkvar_offset_suffix)
        self.offset_zeroed_tkvar.trace_add('write', self.on_tkvar_offset_zeroed)

        # TODO: Find/replace variables
        self.find_text_tkvar = tk.StringVar(top, name='find_text')
        self.find_base_tkvar = tk.IntVar(top, name='find_base')
        self.replace_text_tkvar = tk.StringVar(top, name='replace_text')

    def __init_menus(self):
        menu_bar = tk.Menu(self.top, tearoff=False)
        self.menu_bar = menu_bar

        self.__init_menu_file()
        self.__init_menu_edit()
        self.__init_menu_view()
        self.__init_menu_navigation()
        self.__init_menu_help()

        menu_bar.add_cascade(label='File', underline=0, menu=self.menu_file)
        menu_bar.add_cascade(label='Edit', underline=0, menu=self.menu_edit)
        menu_bar.add_cascade(label='View', underline=0, menu=self.menu_view)
        menu_bar.add_cascade(label='Navigate', underline=0, menu=self.menu_nav)
        menu_bar.add_cascade(label='Help', underline=0, menu=self.menu_help)

        self.top.configure(menu=menu_bar)

    def __init_menu_file(self):
        self.menu_file = menu = tk.Menu(self.top, tearoff=False)

        menu.add_command(label='New', underline=0, accelerator='Ctrl+N', command=self.on_file_new,
                         image=load_image('image/16x16/document_new_thick.png'), compound=tk.LEFT)

        menu.add_command(label='Open', underline=0, accelerator='Ctrl+O', command=self.on_file_open,
                         image=load_image('image/16x16/fileopen.png'), compound=tk.LEFT)

        menu.add_command(label='Import', underline=0, accelerator='Ctrl+I', command=self.on_file_import,
                         image=load_image('image/16x16/fileimport.png'), compound=tk.LEFT)

        menu.add_command(label='Save', underline=0, accelerator='Ctrl+S', command=self.on_file_save,
                         image=load_image('image/16x16/filesave.png'), compound=tk.LEFT)

        menu.add_command(label='Save As', underline=0, accelerator='Ctrl+Shift+S', command=self.on_file_save_as,
                         image=load_image('image/16x16/filesaveas.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Settings', underline=2, accelerator='Ctrl+Shift+T', state=tk.DISABLED,
                         command=self.on_file_settings,
                         image=load_image('image/16x16/configure.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Exit', underline=1, accelerator='Ctrl+W', command=self.on_file_exit,
                         image=load_image('image/16x16/kill.png'), compound=tk.LEFT)

    def __init_menu_edit(self):
        self.menu_edit = menu = tk.Menu(self.top, tearoff=False)

        menu.add_command(label='Undo', underline=1, accelerator='Ctrl+Z', state=tk.DISABLED, command=self.on_edit_undo,
                         image=load_image('image/16x16/undo.png'), compound=tk.LEFT)

        menu.add_command(label='Redo', underline=0, accelerator='Ctrl+Y', state=tk.DISABLED, command=self.on_edit_redo,
                         image=load_image('image/16x16/redo.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Cut', underline=1, accelerator='Ctrl+X', command=self.on_edit_cut,
                         image=load_image('image/16x16/editcut.png'), compound=tk.LEFT)

        menu.add_command(label='Copy', underline=0, accelerator='Ctrl+C', command=self.on_edit_copy,
                         image=load_image('image/16x16/editcopy.png'), compound=tk.LEFT)

        menu.add_command(label='Paste', underline=0, accelerator='Ctrl+V', command=self.on_edit_paste,
                         image=load_image('image/16x16/editpaste.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Cursor mode', underline=7, accelerator='Ins', command=self.on_edit_cursor_mode,
                         image=load_image('image/16x16/edit.png'), compound=tk.LEFT)

        menu.add_command(label='Insert', underline=0, accelerator='+', command=self.on_edit_reserve,
                         image=load_image('image/16x16/document_new.png'), compound=tk.LEFT)

        menu.add_command(label='Delete', underline=0, accelerator='- (Del)', command=self.on_edit_delete,
                         image=load_image('image/16x16/editdelete.png'), compound=tk.LEFT)

        menu.add_command(label='Clear', underline=1, accelerator='. (Del)', command=self.on_edit_clear,
                         image=load_image('image/16x16/eraser.png'), compound=tk.LEFT)

        menu.add_command(label='Fill', underline=0, accelerator='$', command=self.on_edit_fill,
                         image=load_image('image/16x16/fill.png'), compound=tk.LEFT)

        menu.add_command(label='Flood', underline=2, accelerator='%', command=self.on_edit_flood,
                         image=load_image('image/16x16/color_fill.png'), compound=tk.LEFT)

        menu.add_command(label='Crop', underline=0, accelerator='Ctrl+K', command=self.on_edit_crop,
                         image=load_image('image/16x16/crop.png'), compound=tk.LEFT)

        menu.add_command(label='Move', underline=0, accelerator='Ctrl+M',
                         command=self.on_edit_move_focus,
                         image=load_image('image/16x16/move.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Select all', underline=7, accelerator='Ctrl+A', command=self.on_edit_select_all,
                         image=load_image('image/16x16/select-all.png'), compound=tk.LEFT)

        menu.add_command(label='Select range', underline=7, accelerator='Ctrl+R',
                         command=self.on_edit_select_range,
                         image=load_image('image/16x16/select-range.png'), compound=tk.LEFT)

        menu.add_command(label='Copy current address', accelerator='Alt+Ins', command=self.on_edit_copy_address,
                         image=load_image('image/16x16/copy-address.png'), compound=tk.LEFT)

    def __init_menu_view(self):
        self.menu_view = menu = tk.Menu(self.top, tearoff=False)

        # Line submenu
        line = tk.Menu(menu, tearoff=False)
        self.menu_line = line

        for value in LINE_LENGTHS:
            line.add_radiobutton(label=f'{value:3d}', variable=self.line_length_tkvar, value=value)

        line.add_separator()

        line.add_command(label='Custom', command=self.on_view_line_length_custom)

        # Address bits submenu
        bits = tk.Menu(menu, tearoff=False)
        self.menu_line = bits

        for value in ADDRESS_BITS:
            bits.add_radiobutton(label=f'{value:3d}', variable=self.address_bits_tkvar, value=value)

        bits.add_separator()

        bits.add_command(label='Custom', command=self.on_view_address_bits_custom)

        # Encoding submenu
        encm = tk.Menu(menu, tearoff=False)
        self.menu_encoding = encm

        for i, encoding in enumerate(BYTE_ENCODINGS):
            encm.add_radiobutton(label=encoding, variable=self.chars_encoding_tkvar, value=encoding,
                                 columnbreak=(i and not i % 16))

        # Cell submenu
        cell = tk.Menu(menu, tearoff=False)
        self._cell = cell

        cell.add_radiobutton(label='Hex UPPER', underline=0, accelerator='Ctrl+Alt+H',
                             variable=self.cell_mode_tkvar, value=int(ValueFormatEnum.HEXADECIMAL_UPPER),
                             image=load_image('image/16x16/char-hex-upper.png'), compound=tk.LEFT)

        cell.add_radiobutton(label='Hex lower', underline=12, accelerator='Ctrl+Alt+Shift+H',
                             variable=self.cell_mode_tkvar, value=int(ValueFormatEnum.HEXADECIMAL_LOWER),
                             image=load_image('image/16x16/char-hex-lower.png'), compound=tk.LEFT)

        cell.add_radiobutton(label='Decimal', underline=0, accelerator='Ctrl+Alt+D',
                             variable=self.cell_mode_tkvar, value=int(ValueFormatEnum.DECIMAL),
                             image=load_image('image/16x16/char-decimal.png'), compound=tk.LEFT)

        cell.add_radiobutton(label='Octal', underline=0, accelerator='Ctrl+Alt+O',
                             variable=self.cell_mode_tkvar, value=int(ValueFormatEnum.OCTAL),
                             image=load_image('image/16x16/char-octal.png'), compound=tk.LEFT)

        cell.add_radiobutton(label='Binary', underline=0, accelerator='Ctrl+Alt+B',
                             variable=self.cell_mode_tkvar, value=int(ValueFormatEnum.BINARY),
                             image=load_image('image/16x16/char-binary.png'), compound=tk.LEFT)

        cell.add_separator()

        cell.add_checkbutton(label='Prefix', underline=0,
                             variable=self.cell_prefix_tkvar, offvalue=False, onvalue=True)

        cell.add_checkbutton(label='Suffix', underline=0,
                             variable=self.cell_suffix_tkvar, offvalue=False, onvalue=True)

        cell.add_checkbutton(label='Leading zeros', underline=8,
                             variable=self.cell_zeroed_tkvar, offvalue=False, onvalue=True)

        # Address submenu
        address = tk.Menu(menu, tearoff=False)
        self._address = address

        address.add_radiobutton(label='Hex UPPER', underline=0,
                                variable=self.address_mode_tkvar, value=int(ValueFormatEnum.HEXADECIMAL_UPPER),
                                image=load_image('image/16x16/char-hex-upper.png'), compound=tk.LEFT)

        address.add_radiobutton(label='Hex lower', underline=12,
                                variable=self.address_mode_tkvar, value=int(ValueFormatEnum.HEXADECIMAL_LOWER),
                                image=load_image('image/16x16/char-hex-lower.png'), compound=tk.LEFT)

        address.add_radiobutton(label='Decimal', underline=0,
                                variable=self.address_mode_tkvar, value=int(ValueFormatEnum.DECIMAL),
                                image=load_image('image/16x16/char-decimal.png'), compound=tk.LEFT)

        address.add_radiobutton(label='Octal', underline=0,
                                variable=self.address_mode_tkvar, value=int(ValueFormatEnum.OCTAL),
                                image=load_image('image/16x16/char-octal.png'), compound=tk.LEFT)

        address.add_radiobutton(label='Binary', underline=0,
                                variable=self.address_mode_tkvar, value=int(ValueFormatEnum.BINARY),
                                image=load_image('image/16x16/char-binary.png'), compound=tk.LEFT)

        address.add_separator()

        address.add_checkbutton(label='Prefix', underline=0,
                                variable=self.address_prefix_tkvar, offvalue=False, onvalue=True)

        address.add_checkbutton(label='Suffix', underline=0,
                                variable=self.address_suffix_tkvar, offvalue=False, onvalue=True)

        address.add_checkbutton(label='Leading zeros', underline=8,
                                variable=self.address_zeroed_tkvar, offvalue=False, onvalue=True)

        # Offset submenu
        offset = tk.Menu(menu, tearoff=False)
        self._offset = offset

        offset.add_radiobutton(label='Hex UPPER', underline=0,
                               variable=self.offset_mode_tkvar, value=int(ValueFormatEnum.HEXADECIMAL_UPPER),
                               image=load_image('image/16x16/char-hex-upper.png'), compound=tk.LEFT)

        offset.add_radiobutton(label='Hex lower', underline=12,
                               variable=self.offset_mode_tkvar, value=int(ValueFormatEnum.HEXADECIMAL_LOWER),
                               image=load_image('image/16x16/char-hex-lower.png'), compound=tk.LEFT)

        offset.add_radiobutton(label='Decimal', underline=0,
                               variable=self.offset_mode_tkvar, value=int(ValueFormatEnum.DECIMAL),
                               image=load_image('image/16x16/char-decimal.png'), compound=tk.LEFT)

        offset.add_radiobutton(label='Octal', underline=0,
                               variable=self.offset_mode_tkvar, value=int(ValueFormatEnum.OCTAL),
                               image=load_image('image/16x16/char-octal.png'), compound=tk.LEFT)

        offset.add_radiobutton(label='Binary', underline=0,
                               variable=self.offset_mode_tkvar, value=int(ValueFormatEnum.BINARY),
                               image=load_image('image/16x16/char-binary.png'), compound=tk.LEFT)

        offset.add_separator()

        offset.add_checkbutton(label='Prefix', underline=0,
                               variable=self.offset_prefix_tkvar, offvalue=False, onvalue=True)

        offset.add_checkbutton(label='Suffix', underline=0,
                               variable=self.offset_suffix_tkvar, offvalue=False, onvalue=True)

        offset.add_checkbutton(label='Leading zeros', underline=8,
                               variable=self.offset_zeroed_tkvar, offvalue=False, onvalue=True)

        # Menu
        menu.add_cascade(label='Line length', underline=0, menu=line,
                         image=load_image('image/16x16/text_left.png'), compound=tk.LEFT)

        menu.add_cascade(label='Address bits', underline=8, menu=bits,
                         image=load_image('image/16x16/memory.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_cascade(label='Cell format', underline=0, menu=cell,
                         image=load_image('image/16x16/memory-cell.png'), compound=tk.LEFT)

        menu.add_cascade(label='Address format', underline=0, menu=address,
                         image=load_image('image/16x16/memory-address.png'), compound=tk.LEFT)

        menu.add_cascade(label='Offset format', underline=0, menu=offset,
                         image=load_image('image/16x16/memory-offset.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_checkbutton(label='Characters', underline=1,
                             variable=self.chars_visible_tkvar, offvalue=False, onvalue=True)

        menu.add_cascade(label='Encoding', underline=0, menu=encm,
                         image=load_image('image/16x16/fonts.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Redraw', underline=0, accelerator='F5', command=self.on_view_redraw,
                         image=load_image('image/16x16/hotsync.png'), compound=tk.LEFT)

    def __init_menu_navigation(self):
        self.menu_nav = menu = tk.Menu(self.top, tearoff=False)

        menu.add_command(label='Memory address', underline=7, accelerator='Ctrl+G',
                         command=self.on_nav_goto_memory_address_start_focus,
                         image=load_image('image/16x16/goto.png'), compound=tk.LEFT)

        menu.add_command(label='Memory start', underline=7, accelerator='Ctrl+Home',
                         command=self.on_nav_goto_memory_start,
                         image=load_image('image/16x16/top-light.png'), compound=tk.LEFT)

        menu.add_command(label='Memory end', underline=7, accelerator='Ctrl+End',
                         command=self.on_nav_goto_memory_endin,
                         image=load_image('image/16x16/bottom-light.png'), compound=tk.LEFT)

        menu.add_command(label='Memory end-ex', underline=12, accelerator='Ctrl+Alt+End',
                         command=self.on_nav_goto_memory_endex)

        menu.add_command(label='Set address skip', underline=9, command=self.on_nav_address_skip,
                         image=load_image('image/16x16/player_fwd.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Previous block', underline=6, accelerator='Alt+Left',
                         command=self.on_nav_goto_block_previous,
                         image=load_image('image/16x16/arrow-left.png'), compound=tk.LEFT)

        menu.add_command(label='Next block', underline=7, accelerator='Alt+Right',
                         command=self.on_nav_goto_block_next,
                         image=load_image('image/16x16/arrow-right.png'), compound=tk.LEFT)

        menu.add_command(label='Block start', underline=6, accelerator='Alt+Home',
                         command=self.on_nav_goto_block_start,
                         image=load_image('image/16x16/arrow-up-dash.png'), compound=tk.LEFT)

        menu.add_command(label='Block end', underline=7, accelerator='Alt+End',
                         command=self.on_nav_goto_block_endin,
                         image=load_image('image/16x16/arrow-down-dash.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Previous byte', underline=6, accelerator='Ctrl+Left',
                         command=self.on_nav_goto_byte_previous,
                         image=load_image('image/16x16/back-light.png'), compound=tk.LEFT)

        menu.add_command(label='Next byte', underline=6, accelerator='Ctrl+Right',
                         command=self.on_nav_goto_byte_next,
                         image=load_image('image/16x16/next-light.png'), compound=tk.LEFT)

        menu.add_command(label='Line start', underline=6, accelerator='Home',
                         command=self.on_nav_goto_line_start,
                         image=load_image('image/16x16/start-light.png'), compound=tk.LEFT)

        menu.add_command(label='Line end', underline=7, accelerator='End',
                         command=self.on_nav_goto_line_endin,
                         image=load_image('image/16x16/finish-light.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Scroll up', underline=7, accelerator='Ctrl+Up',
                         command=self.on_nav_scroll_line_up,
                         image=load_image('image/16x16/1uparrow.png'), compound=tk.LEFT)

        menu.add_command(label='Scroll down', underline=7, accelerator='Ctrl+Down',
                         command=self.on_nav_scroll_line_down,
                         image=load_image('image/16x16/1downarrow.png'), compound=tk.LEFT)

        menu.add_command(label='Scroll half-page up', underline=18, accelerator='Ctrl+PgUp',
                         command=self.on_nav_scroll_page_up,
                         image=load_image('image/16x16/2uparrow.png'), compound=tk.LEFT)

        menu.add_command(label='Scroll half-page down', underline=19, accelerator='Ctrl+PgDn',
                         command=self.on_nav_scroll_page_down,
                         image=load_image('image/16x16/2downarrow.png'), compound=tk.LEFT)

        menu.add_command(label='Scroll align top', underline=8, accelerator='Ctrl+Alt+PgUp',
                         command=self.on_nav_scroll_top,
                         image=load_image('image/16x16/top.png'), compound=tk.LEFT)

        menu.add_command(label='Scroll align bottom', underline=7, accelerator='Ctrl+Alt+PgDn',
                         command=self.on_nav_scroll_bottom,
                         image=load_image('image/16x16/bottom.png'), compound=tk.LEFT)

    def __init_menu_help(self):
        self.menu_help = menu = tk.Menu(self.top, tearoff=False)

        menu.add_command(label='About', underline=0, command=self.on_help_about,
                         image=load_image('image/16x16/info.png'), compound=tk.LEFT)

    def __init_toolbars(self):
        toolbar_tray = ToolbarTray(self.top, padding=(0, 0), borderwidth=1, relief=tk.SUNKEN)
        self.toolbar_tray = toolbar_tray

        self.__init_toolbar_file()
        self.__init_toolbar_edit()
        self.__init_toolbar_address()
        self.__init_toolbar_blocks()

        toolbar_tray.add_widget(self.toolbar_file)
        toolbar_tray.add_widget(self.toolbar_edit)
        toolbar_tray.add_widget(self.toolbar_address)
        toolbar_tray.add_widget(self.toolbar_blocks)

        toolbar_tray.pack(side=tk.TOP, expand=False, fill=tk.X, anchor=tk.N)

    def __init_toolbar_file(self):
        self.toolbar_file = toolbar = Toolbar(self.toolbar_tray)

        toolbar.add_button(tooltip='New', image=load_image('image/22x22/filenew.png'),
                           command=self.on_file_new)

        toolbar.add_separator()

        toolbar.add_button(tooltip='Open', image=load_image('image/22x22/fileopen.png'),
                           command=self.on_file_open)

        toolbar.add_button(tooltip='Import', image=load_image('image/22x22/fileimport.png'),
                           command=self.on_file_import)

        toolbar.add_separator()

        toolbar.add_button(tooltip='Save', image=load_image('image/22x22/filesave.png'),
                           command=self.on_file_save)

        toolbar.add_button(tooltip='Save As', image=load_image('image/22x22/filesaveas.png'),
                           command=self.on_file_save_as)

        toolbar.add_separator()

        toolbar.add_button(tooltip='Settings', image=load_image('image/22x22/configure.png'),
                           command=self.on_file_settings, state=tk.DISABLED)

        toolbar.finalize()

    def __init_toolbar_edit(self):
        self.toolbar_edit = toolbar = Toolbar(self.toolbar_tray)

        toolbar.add_button(tooltip='Cut', image=load_image('image/22x22/editcut.png'),
                           command=self.on_edit_cut)

        toolbar.add_button(tooltip='Copy',  image=load_image('image/22x22/editcopy.png'),
                           command=self.on_edit_copy)

        toolbar.add_button(tooltip='Paste', image=load_image('image/22x22/editpaste.png'),
                           command=self.on_edit_paste)

        toolbar.add_separator()

        toolbar.add_button(tooltip='Insert', image=load_image('image/22x22/document_new.png'),
                           command=self.on_edit_reserve)

        toolbar.add_button(tooltip='Delete', image=load_image('image/22x22/editdelete.png'),
                           command=self.on_edit_delete)

        toolbar.add_button(tooltip='Clear', image=load_image('image/22x22/eraser.png'),
                           command=self.on_edit_clear)

        toolbar.add_button(tooltip='Fill', image=load_image('image/22x22/fill.png'),
                           command=self.on_edit_fill)

        toolbar.add_button(tooltip='Flood', image=load_image('image/22x22/color_fill.png'),
                           command=self.on_edit_flood)

        toolbar.add_button(tooltip='Crop', image=load_image('image/22x22/crop.png'),
                           command=self.on_edit_crop)

        toolbar.add_separator()

        toolbar.add_button(tooltip='Undo', image=load_image('image/22x22/undo_dark.png'), state=tk.DISABLED,
                           command=self.on_edit_undo)

        toolbar.add_button(tooltip='Redo', image=load_image('image/22x22/redo_dark.png'), state=tk.DISABLED,
                           command=self.on_edit_redo)

        toolbar.finalize()

    def __init_toolbar_address(self):
        self.toolbar_address = toolbar = Toolbar(self.toolbar_tray)

        toolbar.add_button(tooltip='Move to address', image=load_image('image/22x22/move.png'), key='Move',
                           command=self.on_edit_move_apply)

        toolbar.add_button(tooltip='Go to address', image=load_image('image/22x22/goto.png'),
                           command=self.on_nav_goto_memory_address_start_apply)

        self.start_entry = ttk.Entry(toolbar, width=20, justify=tk.RIGHT)
        self.start_entry.bind('<Return>', self.on_nav_goto_memory_address_start_apply)
        self.start_entry.bind('<Escape>', self.on_nav_editor_focus)
        toolbar.add_widget(self.start_entry, key=toolbar.widget_count, tooltip='Start address')

        toolbar.add_button(tooltip='Set current', image=load_image('image/22x22/curfiledir.png'),
                           command=self.on_nav_goto_memory_address_copy)

        self.endin_entry = ttk.Entry(toolbar, width=20, justify=tk.RIGHT)
        self.endin_entry.bind('<Return>', self.on_edit_select_range)
        self.endin_entry.bind('<Escape>', self.on_nav_editor_focus)
        toolbar.add_widget(self.endin_entry, key=toolbar.widget_count, tooltip='End address')

        toolbar.add_button(tooltip='Select range', image=load_image('image/22x22/7days.png'),
                           command=self.on_edit_select_range)

        toolbar.finalize()

    def __init_toolbar_blocks(self):
        self.toolbar_blocks = toolbar = Toolbar(self.toolbar_tray)

        toolbar.add_button(tooltip='Memory start', image=load_image('image/22x22/top.png'),
                           command=self.on_nav_goto_memory_start)

        toolbar.add_button(tooltip='Memory end', image=load_image('image/22x22/bottom.png'),
                           command=self.on_nav_goto_memory_endin)

        toolbar.add_separator()

        toolbar.add_button(tooltip='Previous block', image=load_image('image/22x22/arrow-left.png'),
                           command=self.on_nav_goto_block_previous)

        toolbar.add_button(tooltip='Next block', image=load_image('image/22x22/arrow-right.png'),
                           command=self.on_nav_goto_block_next)

        toolbar.add_separator()

        toolbar.add_button(tooltip='Block start', image=load_image('image/22x22/arrow-up-dash.png'),
                           command=self.on_nav_goto_block_start)

        toolbar.add_button(tooltip='Block end', image=load_image('image/22x22/arrow-down-dash.png'),
                           command=self.on_nav_goto_block_endin)

        toolbar.finalize()

    def __init_statusbar(self):
        self.statusbar_frame = sb_frame = ttk.Frame(self.top)
        self.statusbar_address = sb_address = ttk.Label(sb_frame, anchor=tk.W, relief=tk.SUNKEN, borderwidth=1)
        self.statusbar_selection = sb_selection = ttk.Label(sb_frame, anchor=tk.W, relief=tk.SUNKEN, borderwidth=1)
        self.statusbar_cursor = sb_cursor = ttk.Label(sb_frame, anchor=tk.W, relief=tk.SUNKEN, borderwidth=1)

        sb_address.grid(row=0, column=0, sticky=tk.EW)
        sb_selection.grid(row=0, column=1, sticky=tk.EW)
        sb_cursor.grid(row=0, column=2, sticky=tk.EW)

        sb_frame.rowconfigure(0, weight=0)
        sb_frame.columnconfigure(0, weight=2)
        sb_frame.columnconfigure(1, weight=2)
        sb_frame.columnconfigure(2, weight=1)

        sb_frame.pack(side=tk.BOTTOM, fill=tk.X)

    def __init_editor(self):
        engine = self.engine
        self.editor = editor = EditorWidget(self.top, engine, engine.status)
        editor.pack(side=tk.TOP, expand=True, fill=tk.BOTH)

        self.__init_popup_cell()
        self.__init_popup_address()
        self.__init_popup_offset()
        self.__init_popup_chars()

    def __init_popup_cell(self):
        menu = tk.Menu(tearoff=False)
        self.cells_popup = menu

        # View submenu
        view = tk.Menu(menu, tearoff=False)
        self.cells_popup_view = view

        view.add_radiobutton(label='Hex UPPER', underline=0,
                             variable=self.cell_mode_tkvar, value=int(ValueFormatEnum.HEXADECIMAL_UPPER),
                             image=load_image('image/16x16/char-hex-upper.png'), compound=tk.LEFT)

        view.add_radiobutton(label='Hex lower', underline=12,
                             variable=self.cell_mode_tkvar, value=int(ValueFormatEnum.HEXADECIMAL_LOWER),
                             image=load_image('image/16x16/char-hex-lower.png'), compound=tk.LEFT)

        view.add_radiobutton(label='Decimal', underline=0,
                             variable=self.cell_mode_tkvar, value=int(ValueFormatEnum.DECIMAL),
                             image=load_image('image/16x16/char-decimal.png'), compound=tk.LEFT)

        view.add_radiobutton(label='Octal', underline=0,
                             variable=self.cell_mode_tkvar, value=int(ValueFormatEnum.OCTAL),
                             image=load_image('image/16x16/char-octal.png'), compound=tk.LEFT)

        view.add_radiobutton(label='Binary', underline=0,
                             variable=self.cell_mode_tkvar, value=int(ValueFormatEnum.BINARY),
                             image=load_image('image/16x16/char-binary.png'), compound=tk.LEFT)

        view.add_separator()

        view.add_checkbutton(label='Prefix', underline=0,
                             variable=self.cell_prefix_tkvar, offvalue=False, onvalue=True)

        view.add_checkbutton(label='Suffix', underline=0,
                             variable=self.cell_suffix_tkvar, offvalue=False, onvalue=True)

        view.add_checkbutton(label='Leading zeros', underline=8,
                             variable=self.cell_zeroed_tkvar, offvalue=False, onvalue=True)

        # Menu
        menu.add_cascade(label='Cell format', underline=0, menu=view,
                         image=load_image('image/16x16/memory-cell.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Cut', underline=1, command=self.on_edit_cut,
                         image=load_image('image/16x16/editcut.png'), compound=tk.LEFT)

        menu.add_command(label='Copy', underline=0, command=self.on_edit_copy,
                         image=load_image('image/16x16/editcopy.png'), compound=tk.LEFT)

        menu.add_command(label='Paste', underline=0, command=self.on_edit_paste,
                         image=load_image('image/16x16/editpaste.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Insert', underline=0, command=self.on_edit_reserve,
                         image=load_image('image/16x16/document_new.png'), compound=tk.LEFT)

        menu.add_command(label='Delete', underline=0, command=self.on_edit_delete,
                         image=load_image('image/16x16/editdelete.png'), compound=tk.LEFT)

        menu.add_command(label='Clear', underline=1, command=self.on_edit_clear,
                         image=load_image('image/16x16/eraser.png'), compound=tk.LEFT)

        menu.add_command(label='Fill', underline=0, command=self.on_edit_fill,
                         image=load_image('image/16x16/fill.png'), compound=tk.LEFT)

        menu.add_command(label='Flood', underline=2, command=self.on_edit_flood,
                         image=load_image('image/16x16/color_fill.png'), compound=tk.LEFT)

        menu.add_command(label='Crop', underline=0, command=self.on_edit_crop,
                         image=load_image('image/16x16/crop.png'), compound=tk.LEFT)

        menu.add_command(label='Move', underline=0, command=self.on_edit_move_focus,
                         image=load_image('image/16x16/move.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Export', underline=0, command=self.on_edit_export,
                         image=load_image('image/16x16/fileexport.png'), compound=tk.LEFT)

        self.editor.cells_canvas.bind('<Button-3>', self._on_popup_cell)

    def _on_popup_cell(self, event):
        try:
            self.cells_popup.tk_popup(event.x_root, event.y_root)
        finally:
            self.cells_popup.grab_release()

    def __init_popup_address(self):
        engine = self.engine

        menu = tk.Menu(tearoff=False)
        self.address_popup = menu

        # View submenu
        view = tk.Menu(menu, tearoff=False)
        self.address_popup_view = view

        view.add_radiobutton(label='Hex UPPER', underline=0,
                             variable=self.address_mode_tkvar, value=int(ValueFormatEnum.HEXADECIMAL_UPPER),
                             image=load_image('image/16x16/char-hex-upper.png'), compound=tk.LEFT)

        view.add_radiobutton(label='Hex lower', underline=12,
                             variable=self.address_mode_tkvar, value=int(ValueFormatEnum.HEXADECIMAL_LOWER),
                             image=load_image('image/16x16/char-hex-lower.png'), compound=tk.LEFT)

        view.add_radiobutton(label='Decimal', underline=0,
                             variable=self.address_mode_tkvar, value=int(ValueFormatEnum.DECIMAL),
                             image=load_image('image/16x16/char-decimal.png'), compound=tk.LEFT)

        view.add_radiobutton(label='Octal', underline=0,
                             variable=self.address_mode_tkvar, value=int(ValueFormatEnum.OCTAL),
                             image=load_image('image/16x16/char-octal.png'), compound=tk.LEFT)

        view.add_radiobutton(label='Binary', underline=0,
                             variable=self.address_mode_tkvar, value=int(ValueFormatEnum.BINARY),
                             image=load_image('image/16x16/char-binary.png'), compound=tk.LEFT)

        view.add_separator()

        view.add_checkbutton(label='Prefix', underline=0,
                             variable=self.address_prefix_tkvar, offvalue=False, onvalue=True)

        view.add_checkbutton(label='Suffix', underline=0,
                             variable=self.address_suffix_tkvar, offvalue=False, onvalue=True)

        view.add_checkbutton(label='Leading zeros', underline=8,
                             variable=self.address_zeroed_tkvar, offvalue=False, onvalue=True)

        # Address bits submenu
        bits = tk.Menu(menu, tearoff=False)
        self.menu_line = bits

        for value in ADDRESS_BITS:
            bits.add_radiobutton(label=f'{value:3d}', variable=self.address_bits_tkvar, value=value)

        bits.add_separator()

        bits.add_command(label='Custom', command=self.on_view_address_bits_custom)

        # Menu
        menu.add_cascade(label='Address format', underline=0, menu=view,
                         image=load_image('image/16x16/memory-address.png'), compound=tk.LEFT)

        menu.add_cascade(label='Address bits', underline=8, menu=bits,
                         image=load_image('image/16x16/memory.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Memory address', underline=7, command=self.on_nav_goto_memory_address_start_focus,
                         image=load_image('image/16x16/goto.png'), compound=tk.LEFT)

        menu.add_command(label='Memory start', underline=7, command=self.on_nav_goto_memory_start,
                         image=load_image('image/16x16/top-light.png'), compound=tk.LEFT)

        menu.add_command(label='Memory end', underline=7, command=self.on_nav_goto_memory_endin,
                         image=load_image('image/16x16/bottom-light.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Previous block', underline=6, command=self.on_nav_goto_block_previous,
                         image=load_image('image/16x16/arrow-left.png'), compound=tk.LEFT)

        menu.add_command(label='Next block', underline=7, command=self.on_nav_goto_block_next,
                         image=load_image('image/16x16/arrow-right.png'), compound=tk.LEFT)

        menu.add_command(label='Block start', underline=6, command=self.on_nav_goto_block_start,
                         image=load_image('image/16x16/arrow-up-dash.png'), compound=tk.LEFT)

        menu.add_command(label='Block end', underline=7, command=self.on_nav_goto_block_endin,
                         image=load_image('image/16x16/arrow-down-dash.png'), compound=tk.LEFT)

        self.editor.address_canvas.bind('<Button-3>', self._on_popup_address)

    def _on_popup_address(self, event):
        try:
            self.address_popup.tk_popup(event.x_root, event.y_root)
        finally:
            self.address_popup.grab_release()

    def __init_popup_offset(self):
        engine = self.engine

        menu = tk.Menu(tearoff=False)
        self.offset_popup = menu

        # View submenu
        view = tk.Menu(menu, tearoff=False)
        self.offset_popup_view = view

        view.add_radiobutton(label='Hex UPPER', underline=0,
                             variable=self.offset_mode_tkvar, value=int(ValueFormatEnum.HEXADECIMAL_UPPER),
                             image=load_image('image/16x16/char-hex-upper.png'), compound=tk.LEFT)

        view.add_radiobutton(label='Hex lower', underline=12,
                             variable=self.offset_mode_tkvar, value=int(ValueFormatEnum.HEXADECIMAL_LOWER),
                             image=load_image('image/16x16/char-hex-lower.png'), compound=tk.LEFT)

        view.add_radiobutton(label='Decimal', underline=0,
                             variable=self.offset_mode_tkvar, value=int(ValueFormatEnum.DECIMAL),
                             image=load_image('image/16x16/char-decimal.png'), compound=tk.LEFT)

        view.add_radiobutton(label='Octal', underline=0,
                             variable=self.offset_mode_tkvar, value=int(ValueFormatEnum.OCTAL),
                             image=load_image('image/16x16/char-octal.png'), compound=tk.LEFT)

        view.add_radiobutton(label='Binary', underline=0,
                             variable=self.offset_mode_tkvar, value=int(ValueFormatEnum.BINARY),
                             image=load_image('image/16x16/char-binary.png'), compound=tk.LEFT)

        view.add_separator()

        view.add_checkbutton(label='Prefix', underline=0,
                             variable=self.offset_prefix_tkvar, offvalue=False, onvalue=True)

        view.add_checkbutton(label='Suffix', underline=0,
                             variable=self.offset_suffix_tkvar, offvalue=False, onvalue=True)

        view.add_checkbutton(label='Leading zeros', underline=8,
                             variable=self.offset_zeroed_tkvar, offvalue=False, onvalue=True)

        # Line submenu
        line = tk.Menu(menu, tearoff=False)
        self.offset_popup_line = line

        for value in LINE_LENGTHS:
            line.add_radiobutton(label=f'{value:3d}', variable=self.line_length_tkvar, value=value)

        line.add_separator()

        line.add_command(label='Custom', command=self.on_view_line_length_custom)

        # Menu
        menu.add_cascade(label='Offset format', underline=0, menu=view,
                         image=load_image('image/16x16/memory-offset.png'), compound=tk.LEFT)

        menu.add_cascade(label='Line length', underline=0, menu=line,
                         image=load_image('image/16x16/text_left.png'), compound=tk.LEFT)

        self.editor.offset_canvas.bind('<Button-3>', self._on_popup_offset)

    def _on_popup_offset(self, event):
        try:
            self.offset_popup.tk_popup(event.x_root, event.y_root)
        finally:
            self.offset_popup.grab_release()

    def __init_popup_chars(self):
        menu = tk.Menu(tearoff=False)
        self.chars_popup = menu

        # Encoding submenu
        encm = tk.Menu(menu, tearoff=False)
        self.chars_popup_encoding = encm

        encm.add_command(label='Custom', underline=0, command=self.on_view_chars_encoding_custom)

        encm.add_separator()

        for i, encoding in enumerate(BYTE_ENCODINGS):
            encm.add_radiobutton(label=encoding, variable=self.chars_encoding_tkvar, value=encoding,
                                 columnbreak=(i and not i % 16))

        # Menu
        menu.add_cascade(label='Encoding', underline=0, menu=encm,
                         image=load_image('image/16x16/fonts.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Cut', underline=1, command=self.on_edit_cut,
                         image=load_image('image/16x16/editcut.png'), compound=tk.LEFT)

        menu.add_command(label='Copy', underline=0, command=self.on_edit_copy,
                         image=load_image('image/16x16/editcopy.png'), compound=tk.LEFT)

        menu.add_command(label='Paste', underline=0, command=self.on_edit_paste,
                         image=load_image('image/16x16/editpaste.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Insert', underline=0, command=self.on_edit_reserve,
                         image=load_image('image/16x16/document_new.png'), compound=tk.LEFT)

        menu.add_command(label='Delete', underline=0, command=self.on_edit_delete,
                         image=load_image('image/16x16/editdelete.png'), compound=tk.LEFT)

        menu.add_command(label='Clear', underline=1, command=self.on_edit_clear,
                         image=load_image('image/16x16/eraser.png'), compound=tk.LEFT)

        menu.add_command(label='Fill', underline=0, command=self.on_edit_fill,
                         image=load_image('image/16x16/fill.png'), compound=tk.LEFT)

        menu.add_command(label='Flood', underline=2, command=self.on_edit_flood,
                         image=load_image('image/16x16/color_fill.png'), compound=tk.LEFT)

        menu.add_command(label='Crop', underline=0, command=self.on_edit_crop,
                         image=load_image('image/16x16/crop.png'), compound=tk.LEFT)

        menu.add_command(label='Move', underline=0, command=self.on_edit_move_focus,
                         image=load_image('image/16x16/move.png'), compound=tk.LEFT)

        menu.add_separator()

        menu.add_command(label='Export', underline=0, command=self.on_edit_export,
                         image=load_image('image/16x16/fileexport.png'), compound=tk.LEFT)

        self.editor.chars_canvas.bind('<Button-3>', self._on_popup_chars)

    def _on_popup_chars(self, event):
        try:
            self.chars_popup.tk_popup(event.x_root, event.y_root)
        finally:
            self.chars_popup.grab_release()

    def update_status(self):
        status = self.engine.status
        format_address = status.address_format_string.format

        if status.sel_mode == SelectionMode.NORMAL:
            start, endin = status.sel_start_address, status.sel_endin_address
            if endin < start:
                endin, start = start, endin
            text_range = f'Range: {format_address(start)} - {format_address(endin)}'
            length = endin + 1 - start
            text_length = f'Size: {format_address(length)} = {length:d}'

        elif status.sel_mode == SelectionMode.RECTANGLE:
            start_x, start_y = status.sel_start_cell
            endin_x, endin_y = status.sel_endin_cell
            if endin_x < start_x:
                endin_x, start_x = start_x, endin_x
            if endin_y < start_y:
                endin_y, start_y = start_y, endin_y
            text_range = f'Range: ({start_x:d}, {start_y:d}) - ({endin_x:d}, {endin_y:d})'
            text_w = endin_x + 1 - start_x
            text_h = endin_y + 1 - start_y
            text_length = f'Size: ({text_w:d}, {text_h:d}) = ({text_w:X}h, {text_h:X}h)'

        else:
            address = status.cursor_address
            text_range = f'Address: {format_address(address)}'
            text_length = f'Digit: {status.cell_format_length - status.cursor_digit}'

        self.statusbar_address.configure(text=text_range)
        self.statusbar_selection.configure(text=text_length)

        mode_text = f'{status.cursor_mode.name.lower()}'
        if status.sel_mode:
            mode_text += f' / {status.sel_mode.name.lower()}'
        self.statusbar_cursor.configure(text=mode_text)

    def get_start_text(self) -> str:
        text = self.start_entry.get()
        return text

    def set_start_text(self, text: str, focus: bool = False) -> None:
        start_entry = self.start_entry
        start_entry.delete(0, tk.END)
        if text:
            start_entry.insert(tk.END, text)
        if focus:
            start_entry.focus_set()

    def focus_start_text(self) -> None:
        start_entry = self.start_entry
        start_entry.focus_set()

    def get_start_address(self) -> Address:
        text = self.get_start_text()
        address = parse_int(text)[0]
        return address

    def set_start_address(self, address: Address) -> None:
        fmt = self.engine.status.address_format_string
        text = fmt.format(address)
        self.set_start_text(text)

    def get_endin_text(self) -> str:
        text = self.endin_entry.get()
        return text

    def set_endin_text(self, text: str, focus: bool = False) -> None:
        endin_entry = self.endin_entry
        endin_entry.delete(0, tk.END)
        if text:
            endin_entry.insert(tk.END, text)
        if focus:
            endin_entry.focus_set()

    def focus_endin_text(self) -> None:
        endin_entry = self.endin_entry
        endin_entry.focus_set()

    def get_endin_address(self) -> Address:
        text = self.get_endin_text()
        address = parse_int(text)[0]
        return address

    def set_endin_address(self, address: Address) -> None:
        fmt = self.engine.status.address_format_string
        text = fmt.format(address)
        self.set_endin_text(text)

    def show_about(self):  # TODO: make better dedicated window
        tk.messagebox.showinfo('About Hecks!', (
            'Copyright (c) 2021, Andrea Zoppi. All rights reserved.\n'
            '\n'
            'Hecks is free software: you can redistribute it and/or modify '
            'it under the terms of the GNU General Public License as published by '
            'the Free Software Foundation, either version 3 of the License, or '
            '(at your option) any later version.\n'
            '\n'
            'Hecks is distributed in the hope that it will be useful, '
            'but WITHOUT ANY WARRANTY; without even the implied warranty of '
            'MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the '
            'GNU General Public License for more details.\n'
            '\n'
            'You should have received a copy of the GNU General Public License '
            'along with Hecks.  If not, see <https://www.gnu.org/licenses/>.'
        ))

    def show_info(self, title: str, message: str):
        tk.messagebox.showinfo(title=title, message=message)

    def show_warning(self, title: str, message: str):
        tk.messagebox.showwarning(title=title, message=message)

    def show_error(self, title: str, message: str):
        tk.messagebox.showerror(title=title, message=message)

    def ask_open_file_path(self) -> Optional[str]:
        file_path = tk.filedialog.askopenfilename(filetypes=FILE_TYPES)
        return file_path

    def ask_save_file_path(self) -> Optional[str]:
        file_path = tk.filedialog.asksaveasfilename(filetypes=FILE_TYPES)
        return file_path

    def ask_line_length_custom(self) -> Optional[int]:
        value = tk.simpledialog.askinteger('Line length', 'Enter the line length:')
        if value is not None:
            if 1 <= value <= 256:
                self.line_length_tkvar.set(value)
                return value
            else:
                tk.messagebox.showerror('Invalid value', 'Only positive integers between 1 and 256 are accepted')
        return None

    def ask_address_bits_custom(self) -> Optional[int]:
        value = tk.simpledialog.askinteger('Address bits', 'Enter the address bit size:')
        if value is not None:
            if 1 <= value <= 256:
                self.address_bits_tkvar.set(value)
                return value
            else:
                tk.messagebox.showerror('Invalid value', 'Only positive integers between 1 and 256 are accepted')
        return None

    def ask_address_skip_custom(self) -> Optional[int]:
        text = tk.simpledialog.askstring('Address skip', 'Enter the address skip:')
        if text is not None:
            try:
                value = parse_int(text)[0]
            except ValueError:
                tk.messagebox.showerror('Invalid value', 'Invalid address value format')
            else:
                self.address_skip_tkvar.set(value)
                return value
        return None

    def ask_chars_encoding_custom(self) -> Optional[str]:
        value = tk.simpledialog.askstring('Text encoding', 'Enter the Python text codec name:')
        if value is not None:
            try:
                b'\0'.decode(encoding=value, errors='strict')
            except UnicodeDecodeError:
                tk.messagebox.showerror('Invalid encoding', f'Python does not support the text codec: {value!r}')
            else:
                self.chars_encoding_tkvar.set(value)
                return value
        return None

    def update_title_by_file_path(self):
        top = self.top
        status = self.engine.status

        if status.file_path:
            text = f'{status.file_path} - {PROGRAM_TITLE}'
        else:
            text = f'|untitled| - {PROGRAM_TITLE}'
        top.title(text)

    def update_menus_by_selection(self):
        status = self.engine.status
        # TODO: cache condition to skip useless GUI calls
        state = tk.NORMAL if status.sel_mode else tk.DISABLED

        menu = self.menu_edit
        labels = ('Cut', 'Copy', 'Crop', 'Move')
        for label in labels:
            menu.entryconfigure(menu.index(label), state=state)

        menu = self.cells_popup
        labels = ('Cut', 'Copy', 'Crop', 'Move', 'Export')
        for label in labels:
            menu.entryconfigure(menu.index(label), state=state)

        menu = self.chars_popup
        labels = ('Cut', 'Copy', 'Crop', 'Move', 'Export')
        for label in labels:
            menu.entryconfigure(menu.index(label), state=state)

        toolbar = self.toolbar_edit
        labels = ('Cut', 'Copy', 'Crop')
        for label in labels:
            toolbar.get_widget(label).configure(cnf=dict(state=state))

        toolbar = self.toolbar_address
        labels = ('Move',)
        for label in labels:
            toolbar.get_widget(label).configure(cnf=dict(state=state))

        self.update_menus_by_cursor()

    def update_menus_by_cursor(self):
        status = self.engine.status
        address = status.cursor_address
        memory = status.memory
        start = memory.start
        endex = memory.endex

        # TODO: cache condition to skip useless GUI calls
        if status.sel_mode or start <= address < endex:
            state = tk.NORMAL
        else:
            state = tk.DISABLED

        menu = self.menu_edit
        labels = ('Fill',)
        for label in labels:
            menu.entryconfigure(menu.index(label), state=state)

        menu = self.cells_popup
        labels = ('Fill',)
        for label in labels:
            menu.entryconfigure(menu.index(label), state=state)

        toolbar = self.toolbar_edit
        labels = ('Fill',)
        for label in labels:
            toolbar.get_widget(label).configure(state=state)

        # TODO: cache condition to skip useless GUI calls
        if status.sel_mode or (start <= address < endex and memory.peek(address) is None):
            state = tk.NORMAL
        else:
            state = tk.DISABLED

        menu = self.menu_edit
        labels = ('Flood',)
        for label in labels:
            menu.entryconfigure(menu.index(label), state=state)

        menu = self.cells_popup
        labels = ('Flood',)
        for label in labels:
            menu.entryconfigure(menu.index(label), state=state)

        toolbar = self.toolbar_edit
        labels = ('Flood',)
        for label in labels:
            toolbar.get_widget(label).configure(state=state)

    def on_file_new(self, event=None):
        self.engine.on_file_new()

    def on_file_open(self, event=None):
        self.engine.on_file_open()

    def on_file_import(self, event=None):
        self.engine.on_file_import()

    def on_file_save(self, event=None):
        self.engine.on_file_save()

    def on_file_save_as(self, event=None):
        self.engine.on_file_save_as()

    def on_file_settings(self, event=None):
        self.engine.on_file_settings()

    def on_file_exit(self, event=None):
        self.engine.on_file_exit()

    def on_edit_undo(self, event=None):
        self.engine.on_edit_undo()

    def on_edit_redo(self, event=None):
        self.engine.on_edit_redo()

    def on_edit_cut(self, event=None):
        self.engine.on_edit_cut()

    def on_edit_copy(self, event=None):
        self.engine.on_edit_copy()

    def on_edit_paste(self, event=None):
        self.engine.on_edit_paste()

    def on_edit_delete(self, event=None):
        self.engine.on_edit_delete()

    def on_edit_cursor_mode(self, event=None):
        self.engine.on_edit_cursor_mode()

    def on_edit_clear(self, event=None):
        self.engine.on_edit_clear()

    def on_edit_reserve(self, event=None):
        self.engine.on_edit_reserve()

    def on_edit_fill(self, event=None):
        self.engine.on_edit_fill()

    def on_edit_flood(self, event=None):
        self.engine.on_edit_flood()

    def on_edit_crop(self, event=None):
        self.engine.on_edit_crop()

    def on_edit_move_focus(self, event=None):
        self.engine.on_edit_move_focus()

    def on_edit_move_apply(self, event=None):
        self.engine.on_edit_move_apply()

    def on_edit_export(self, event=None):
        self.engine.on_edit_export()

    def on_edit_select_all(self, event=None):
        self.engine.on_edit_select_all()

    def on_edit_select_range(self, event=None):
        self.engine.on_edit_select_range()

    def on_edit_copy_address(self, event=None):
        self.engine.on_edit_copy_address()

    def on_edit_find(self, event=None):
        self.engine.on_edit_find()

    def on_view_line_length_custom(self, event=None):
        self.engine.on_view_line_length_custom()

    def on_view_address_bits_custom(self, event=None):
        self.engine.on_view_address_bits_custom()

    def on_view_chars_encoding_custom(self, event=None):
        self.engine.on_view_chars_encoding_custom()

    def on_view_redraw(self, event=None):
        self.engine.on_view_redraw()

    def on_nav_editor_focus(self, event=None):
        self.engine.on_nav_editor_focus()

    def on_nav_goto_memory_address_start_focus(self, event=None):
        self.engine.on_nav_goto_memory_address_start_focus()

    def on_nav_goto_memory_address_start_apply(self, event=None):
        self.engine.on_nav_goto_memory_address_start_apply()

    def on_nav_goto_memory_address_endin_focus(self, event=None):
        self.engine.on_nav_goto_memory_address_endin_focus()

    def on_nav_goto_memory_address_endin_apply(self, event=None):
        self.engine.on_nav_goto_memory_address_endin_apply()

    def on_nav_goto_memory_address_copy(self, event=None):
        self.engine.on_nav_goto_memory_address_copy()

    def on_nav_goto_memory_start(self, event=None):
        self.engine.on_nav_goto_memory_start()

    def on_nav_goto_memory_endin(self, event=None):
        self.engine.on_nav_goto_memory_endin()

    def on_nav_goto_memory_endex(self, event=None):
        self.engine.on_nav_goto_memory_endex()

    def on_nav_address_skip(self, event=None):
        self.engine.on_nav_address_skip()

    def on_nav_goto_block_previous(self, event=None):
        self.engine.on_nav_goto_block_previous()

    def on_nav_goto_block_next(self, event=None):
        self.engine.on_nav_goto_block_next()

    def on_nav_goto_block_start(self, event=None):
        self.engine.on_nav_goto_block_start()

    def on_nav_goto_block_endin(self, event=None):
        self.engine.on_nav_goto_block_endin()

    def on_nav_goto_byte_previous(self, event=None):
        self.engine.on_nav_goto_byte_previous()

    def on_nav_goto_byte_next(self, event=None):
        self.engine.on_nav_goto_byte_next()

    def on_nav_goto_line_start(self, event=None):
        self.engine.on_nav_goto_line_start()

    def on_nav_goto_line_endin(self, event=None):
        self.engine.on_nav_goto_line_endin()

    def on_nav_scroll_line_up(self, event=None):
        self.engine.on_nav_scroll_line_up()

    def on_nav_scroll_line_down(self, event=None):
        self.engine.on_nav_scroll_line_down()

    def on_nav_scroll_page_up(self, event=None):
        self.engine.on_nav_scroll_page_up()

    def on_nav_scroll_page_down(self, event=None):
        self.engine.on_nav_scroll_page_down()

    def on_nav_scroll_top(self, event=None):
        self.engine.on_nav_scroll_top()

    def on_nav_scroll_bottom(self, event=None):
        self.engine.on_nav_scroll_bottom()

    def on_help_about(self, event=None):
        self.engine.on_help_about()

    def on_tkvar_chars_visible(self, *args):
        value = self.top.getvar(name='chars_visible')
        self.engine.on_set_chars_visible(value)

    def on_tkvar_line_length(self, *args):
        value = self.top.getvar(name='line_length')
        self.engine.on_set_line_length(value)

    def on_tkvar_chars_encoding(self, *args):
        value = self.top.getvar(name='chars_encoding')
        self.engine.on_set_chars_encoding(value)

    def on_tkvar_cell_mode(self, *args):
        value = self.top.getvar(name='cell_mode')
        self.engine.on_set_cell_mode(value)

    def on_tkvar_cell_prefix(self, *args):
        value = self.top.getvar(name='cell_prefix')
        self.engine.on_set_cell_prefix(value)

    def on_tkvar_cell_suffix(self, *args):
        value = self.top.getvar(name='cell_suffix')
        self.engine.on_set_cell_suffix(value)

    def on_tkvar_cell_zeroed(self, *args):
        value = self.top.getvar(name='cell_zeroed')
        self.engine.on_set_cell_zeroed(value)

    def on_tkvar_address_mode(self, *args):
        value = self.top.getvar(name='address_mode')
        self.engine.on_set_address_mode(value)

    def on_tkvar_address_prefix(self, *args):
        value = self.top.getvar(name='address_prefix')
        self.engine.on_set_address_prefix(value)

    def on_tkvar_address_suffix(self, *args):
        value = self.top.getvar(name='address_suffix')
        self.engine.on_set_address_suffix(value)

    def on_tkvar_address_zeroed(self, *args):
        value = self.top.getvar(name='address_zeroed')
        self.engine.on_set_address_zeroed(value)

    def on_tkvar_address_skip(self, *args):
        value = self.top.getvar(name='address_skip')
        self.engine.on_set_address_skip(value)

    def on_tkvar_address_bits(self, *args):
        value = self.top.getvar(name='address_bits')
        self.engine.on_set_address_bits(value)

    def on_tkvar_offset_mode(self, *args):
        value = self.top.getvar(name='offset_mode')
        self.engine.on_set_offset_mode(value)

    def on_tkvar_offset_prefix(self, *args):
        value = self.top.getvar(name='offset_prefix')
        self.engine.on_set_offset_prefix(value)

    def on_tkvar_offset_suffix(self, *args):
        value = self.top.getvar(name='offset_suffix')
        self.engine.on_set_offset_suffix(value)

    def on_tkvar_offset_zeroed(self, *args):
        value = self.top.getvar(name='offset_zeroed')
        self.engine.on_set_offset_zeroed(value)


# =====================================================================================================================

class InstanceManager(BaseInstanceManager):

    def __init__(self):
        super().__init__()

        # Create a hidden root window, not used by the application
        # root = tk.Tk()
        root = ttkthemes.ThemedTk(theme=_THEME)
        root.overrideredirect(True)
        root.withdraw()
        # self._root: tk.Tk = root
        self._root: ttkthemes.ThemedTk = root
        _fix_global_colors(root)

    def remove(self, index: int) -> object:
        instance = super().remove(index)
        if self:
            return instance
        else:
            self.quit()
            return None

    def run(self):
        self._root.mainloop()

    def quit(self) -> None:
        super().quit()
        self._root.destroy()

    @property
    # def root(self) -> tk.Tk:
    def root(self) -> ttkthemes.ThemedTk:
        return self._root


# =====================================================================================================================

def main() -> None:
    manager = InstanceManager()
    UserInterface(manager, Engine)
    manager.run()


if __name__ == '__main__':
    main()
