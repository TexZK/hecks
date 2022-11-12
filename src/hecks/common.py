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

import abc
import enum
from math import floor
from typing import List
from typing import MutableMapping
from typing import Optional
from typing import Tuple

from bytesparse.base import Address
from bytesparse.base import Value
from bytesparse.inplace import Memory

from .utils import VALUE_FORMAT_CHAR
from .utils import VALUE_FORMAT_PREFIX
from .utils import VALUE_FORMAT_SUFFIX
from .utils import ValueFormatEnum


# =====================================================================================================================

FloatCoord = float
FloatCoords = Tuple[FloatCoord, FloatCoord]

CharCoord = int
CharCoords = Tuple[CharCoord, CharCoord]

CellCoord = int
CellCoords = Tuple[CellCoord, CellCoord]

InstanceIndex = int


PROGRAM_TITLE: str = 'Hecks!'

BIG_SELECTION_SIZE: Address = 1 << 28

LINE_LENGTHS = (8, 16, 24, 32, 64, 128, 256)

ADDRESS_BITS = (8, 10, 12, 14, 16, 18, 20, 24, 32, 48, 64)


# =====================================================================================================================

@enum.unique
class CursorMode(enum.IntEnum):
    OVERWRITE = 0
    INSERT = 1


@enum.unique
class SelectionMode(enum.IntEnum):
    OFF = 0
    NORMAL = 1
    RECTANGLE = 2  # TODO


# =====================================================================================================================

BYTE_ENCODINGS: List[str] = [
    'ascii',
    'cp437',
    'cp737',
    'cp850',
    'cp852',
    'cp855',
    'cp857',
    'cp858',
    'cp860',
    'cp861',
    'cp862',
    'cp863',
    'cp864',
    'cp865',
    'cp866',
    'cp869',
    'cp874',
    'cp932',
    'cp949',
    'cp950',
    'cp1250',
    'cp1251',
    'cp1252',
    'cp1253',
    'cp1254',
    'cp1255',
    'cp1256',
    'cp1257',
    'cp1258',
    'latin_1',
    'iso8859_2',
    'iso8859_3',
    'iso8859_4',
    'iso8859_5',
    'iso8859_6',
    'iso8859_7',
    'iso8859_8',
    'iso8859_9',
    'iso8859_10',
    'iso8859_11',
    'iso8859_12',
    'iso8859_13',
    'iso8859_14',
    'iso8859_15',
    'iso8859_16',
]


def build_encoding_table(encoding: str, nonprintable: str = '.') -> List[str]:
    lut = []
    for i in range(256):
        try:
            t = bytes([i]).decode(encoding=encoding)
        except UnicodeError:
            t = nonprintable
        lut.append(t if t.isprintable() else nonprintable)
    return lut


# =====================================================================================================================

class EngineStatus:

    def __init__(self):
        # File properties
        self.file_path: Optional[str] = None

        # Initialize memory
        # XXX FIXME DEBUG: allocate some dummy data for debug
        data = bytes(range(256)) * 8
        self.memory = Memory.from_bytes(data, offset=0xDA7A0000)

        self.line_length: int = 16
        self.chars_encoding = 'ascii'
        self.chars_table = build_encoding_table(self.chars_encoding)

        # Allocate cell attributes
        self.cell_format_mode: ValueFormatEnum = ValueFormatEnum.HEXADECIMAL_UPPER
        self.cell_format_string: str = ''
        self.cell_format_length: int = 0
        self.cell_format_zeroed: bool = True
        self.cell_format_prefix: bool = False
        self.cell_format_suffix: bool = False

        # Allocate address attributes
        self.address_format_mode: ValueFormatEnum = ValueFormatEnum.HEXADECIMAL_UPPER
        self.address_format_string: str = ''
        self.address_format_length: int = 0
        self.address_format_zeroed: bool = True
        self.address_format_prefix: bool = False
        self.address_format_suffix: bool = True
        self.address_skip: Address = 0
        self.address_bits: int = 32
        self.address_max: Address = (1 << self.address_bits) - 1
        self.address_min: Address = 0

        # Allocate offset attributes
        self.offset_format_mode: ValueFormatEnum = ValueFormatEnum.HEXADECIMAL_UPPER
        self.offset_format_string: str = ''
        self.offset_format_length: int = 0
        self.offset_format_zeroed: bool = True
        self.offset_format_prefix: bool = False
        self.offset_format_suffix: bool = False

        # Configure value formats
        self.cell_spacing: int = 0
        self.offset_spacing: int = 0

        self.update_cell_format()
        self.update_address_format()
        self.update_offset_format()

        # Selection status
        self.sel_mode: SelectionMode = SelectionMode.OFF

        self.sel_start_cell: CellCoords = (-1, -1)
        self.sel_start_address: Address = 0

        self.sel_endin_cell: CellCoords = (-1, -1)
        self.sel_endin_address: Address = 0

        # Cursor status
        self.cursor_mode: CursorMode = CursorMode.OVERWRITE
        self.cursor_cell: CellCoords = (0, 0)
        self.cursor_digit: CellCoord = 0  # digit index, left-to-right
        self.cursor_address: Address = 0

    def address_to_cell_coords(self, address: Address) -> CellCoords:
        address -= self.address_skip
        line_length = self.line_length
        cell_y = address // line_length
        cell_x = address - (cell_y * line_length)
        return cell_x, cell_y

    def cell_coords_to_address(self, cell_x: CellCoord, cell_y: CellCoord) -> Address:
        line_length = self.line_length
        cell_x = max(0, min(floor(cell_x), line_length - 1))
        cell_y = floor(cell_y)
        address = (line_length * cell_y) + cell_x
        address += self.address_skip
        return address

    def update_cell_format(self) -> None:
        offset_spacing_before = self.offset_spacing
        cell_format_length_before = self.cell_format_length

        value_bits = 8
        value_max = (1 << value_bits) - 1

        mode = self.cell_format_mode
        format_char = VALUE_FORMAT_CHAR[mode]
        format_prefix = VALUE_FORMAT_PREFIX[mode] if self.cell_format_prefix else ''
        format_suffix = VALUE_FORMAT_SUFFIX[mode] if self.cell_format_suffix else ''
        format_zero = '0' if self.cell_format_zeroed else ''
        format_width = len('{{:{}}}'.format(format_char).format(value_max))
        format_string = f'{format_prefix}{{:{format_zero}{format_width}{format_char}}}{format_suffix}'
        format_length = len(format_string.format(value_max))

        self.cell_format_string = format_string
        self.cell_format_length = format_length

        self.cell_spacing = 1 + max(0, self.offset_format_length - self.cell_format_length)
        self.offset_spacing = 1 + max(0, self.cell_format_length - self.offset_format_length)

        if ((offset_spacing_before != self.offset_spacing or
             cell_format_length_before != self.cell_format_length)):
            self.update_offset_format()

    def update_address_format(self) -> None:
        address_bits = self.address_bits
        address_max = (1 << address_bits) - 1
        self.address_max = address_max
        self.address_min = 0

        mode = self.address_format_mode
        format_char = VALUE_FORMAT_CHAR[mode]
        format_prefix = VALUE_FORMAT_PREFIX[mode] if self.address_format_prefix else ''
        format_suffix = VALUE_FORMAT_SUFFIX[mode] if self.address_format_suffix else ''
        format_zero = '0' if self.address_format_zeroed else ''
        format_width = len('{{:{}}}'.format(format_char).format(address_max))
        format_string = f'{format_prefix}{{:{format_zero}{format_width}{format_char}}}{format_suffix}'
        format_length = len(format_string.format(address_max))

        self.address_format_string = format_string
        self.address_format_length = format_length

    def update_offset_format(self) -> None:
        cell_spacing_before = self.cell_spacing
        offset_format_length_before = self.offset_format_length

        value_bits = 8
        value_max = (1 << value_bits) - 1

        mode = self.offset_format_mode
        format_char = VALUE_FORMAT_CHAR[mode]
        format_prefix = VALUE_FORMAT_PREFIX[mode] if self.offset_format_prefix else ''
        format_suffix = VALUE_FORMAT_SUFFIX[mode] if self.offset_format_suffix else ''
        format_zero = '0' if self.offset_format_zeroed else ''
        format_width = len('{{:{}}}'.format(format_char).format(value_max))
        format_string = f'{format_prefix}{{:{format_zero}{format_width}{format_char}}}{format_suffix}'
        format_length = len(format_string.format(value_max))

        self.offset_format_string = format_string
        self.offset_format_length = format_length

        self.cell_spacing = 1 + max(0, self.offset_format_length - self.cell_format_length)
        self.offset_spacing = 1 + max(0, self.cell_format_length - self.offset_format_length)

        if ((cell_spacing_before != self.cell_spacing or
             offset_format_length_before != self.offset_format_length)):
            self.update_cell_format()


# ---------------------------------------------------------------------------------------------------------------------

class EngineFileCallbacks(abc.ABC):

    @abc.abstractmethod
    def on_file_new(self) -> None:
        ...

    @abc.abstractmethod
    def on_file_open(self) -> None:
        ...

    @abc.abstractmethod
    def on_file_import(self) -> None:
        ...

    @abc.abstractmethod
    def on_file_save(self) -> None:
        ...

    @abc.abstractmethod
    def on_file_save_as(self) -> None:
        ...

    @abc.abstractmethod
    def on_file_settings(self) -> None:
        ...

    @abc.abstractmethod
    def on_file_exit(self) -> None:
        ...


# ---------------------------------------------------------------------------------------------------------------------

class EngineEditCallbacks(abc.ABC):

    @abc.abstractmethod
    def on_edit_undo(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_redo(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_cut(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_copy(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_paste(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_delete(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_cursor_mode(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_clear(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_reserve(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_fill(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_flood(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_crop(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_move_focus(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_move_apply(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_export(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_select_all(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_select_range(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_copy_address(self) -> None:
        ...

    @abc.abstractmethod
    def on_edit_find(self) -> None:
        ...


# ---------------------------------------------------------------------------------------------------------------------

class EngineViewCallbacks(abc.ABC):

    @abc.abstractmethod
    def on_view_line_length_custom(self) -> None:
        ...

    @abc.abstractmethod
    def on_view_address_bits_custom(self) -> None:
        ...

    @abc.abstractmethod
    def on_view_chars_encoding_custom(self) -> None:
        ...

    @abc.abstractmethod
    def on_view_redraw(self) -> None:
        ...


# ---------------------------------------------------------------------------------------------------------------------

class EngineNavigationCallbacks(abc.ABC):

    @abc.abstractmethod
    def on_nav_editor_focus(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_memory_address_start_focus(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_memory_address_start_apply(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_memory_address_endin_focus(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_memory_address_endin_apply(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_memory_address_copy(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_memory_start(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_memory_endin(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_memory_endex(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_address_skip(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_block_previous(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_block_next(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_block_start(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_block_endin(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_byte_previous(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_byte_next(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_line_start(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_goto_line_endin(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_scroll_line_up(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_scroll_line_down(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_scroll_page_up(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_scroll_page_down(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_scroll_top(self) -> None:
        ...

    @abc.abstractmethod
    def on_nav_scroll_bottom(self) -> None:
        ...


# ---------------------------------------------------------------------------------------------------------------------

class EngineHelpCallbacks(abc.ABC):

    @abc.abstractmethod
    def on_help_about(self) -> None:
        ...


# ---------------------------------------------------------------------------------------------------------------------

class EngineSetCallbacks(abc.ABC):

    @abc.abstractmethod
    def on_set_chars_visible(self, visible: bool) -> None:
        ...

    @abc.abstractmethod
    def on_set_line_length(self, line_length: CellCoord) -> None:
        ...

    @abc.abstractmethod
    def on_set_chars_encoding(self, encoding: str) -> None:
        ...

    @abc.abstractmethod
    def on_set_cell_mode(self, mode: ValueFormatEnum) -> None:
        ...

    @abc.abstractmethod
    def on_set_cell_prefix(self, prefix: bool) -> None:
        ...

    @abc.abstractmethod
    def on_set_cell_suffix(self, suffix: bool) -> None:
        ...

    @abc.abstractmethod
    def on_set_cell_zeroed(self, zeroed: bool) -> None:
        ...

    @abc.abstractmethod
    def on_set_address_mode(self, mode: ValueFormatEnum) -> None:
        ...

    @abc.abstractmethod
    def on_set_address_prefix(self, prefix: bool) -> None:
        ...

    @abc.abstractmethod
    def on_set_address_suffix(self, suffix: bool) -> None:
        ...

    @abc.abstractmethod
    def on_set_address_zeroed(self, zeroed: bool) -> None:
        ...

    @abc.abstractmethod
    def on_set_address_skip(self, skip: Address) -> None:
        ...

    @abc.abstractmethod
    def on_set_address_bits(self, bitsize: int) -> None:
        ...

    @abc.abstractmethod
    def on_set_offset_mode(self, mode: ValueFormatEnum) -> None:
        ...

    @abc.abstractmethod
    def on_set_offset_prefix(self, prefix: bool) -> None:
        ...

    @abc.abstractmethod
    def on_set_offset_suffix(self, suffix: bool) -> None:
        ...

    @abc.abstractmethod
    def on_set_offset_zeroed(self, zeroed: bool) -> None:
        ...


# ---------------------------------------------------------------------------------------------------------------------

class EngineEditorCallbacks(abc.ABC):

    @abc.abstractmethod
    def on_key_digit_cells(self, digit: Value):
        ...

    @abc.abstractmethod
    def on_key_digit_chars(self, digit: Value):
        ...

    @abc.abstractmethod
    def on_key_reserve_cell(self):
        ...

    @abc.abstractmethod
    def on_key_delete_cell(self):
        ...

    @abc.abstractmethod
    def on_key_clear_cell(self):
        ...

    @abc.abstractmethod
    def on_key_clear_back(self):
        ...

    @abc.abstractmethod
    def on_key_clear_next(self):
        ...

    @abc.abstractmethod
    def on_key_delete(self):
        ...

    @abc.abstractmethod
    def on_key_fill(self):
        ...

    @abc.abstractmethod
    def on_key_flood(self):
        ...

    @abc.abstractmethod
    def on_key_cut(self):
        ...

    @abc.abstractmethod
    def on_key_copy(self):
        ...

    @abc.abstractmethod
    def on_key_paste(self):
        ...

    @abc.abstractmethod
    def on_key_crop(self):
        ...

    @abc.abstractmethod
    def on_key_move_focus(self):
        ...

    @abc.abstractmethod
    def on_key_move_apply(self):
        ...

    @abc.abstractmethod
    def on_key_scroll_line_up(self):
        ...

    @abc.abstractmethod
    def on_key_scroll_page_up(self):
        ...

    @abc.abstractmethod
    def on_key_scroll_line_down(self):
        ...

    @abc.abstractmethod
    def on_key_scroll_page_down(self):
        ...

    @abc.abstractmethod
    def on_key_scroll_top(self):
        ...

    @abc.abstractmethod
    def on_key_scroll_bottom(self):
        ...

    @abc.abstractmethod
    def on_key_move_left_digit(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_move_right_digit(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_move_left_byte(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_move_right_byte(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_move_line_up(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_move_page_up(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_move_line_down(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_move_page_down(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_goto_line_start(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_goto_line_endin(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_goto_memory_apply(self):
        ...

    @abc.abstractmethod
    def on_key_goto_memory_focus(self):
        ...

    @abc.abstractmethod
    def on_key_goto_memory_start(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_goto_memory_endin(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_goto_memory_endex(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_goto_block_previous(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_goto_block_next(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_goto_block_start(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_goto_block_endin(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def on_key_copy_address(self):
        ...

    @abc.abstractmethod
    def on_key_set_address(self):
        ...

    @abc.abstractmethod
    def on_key_select_all(self):
        ...

    @abc.abstractmethod
    def on_key_select_range(self):
        ...

    @abc.abstractmethod
    def on_key_escape_selection(self):
        ...

    @abc.abstractmethod
    def on_key_switch_cursor_mode(self):
        ...

    @abc.abstractmethod
    def on_key_redraw(self):
        ...

    @abc.abstractmethod
    def on_key_undo(self):
        ...

    @abc.abstractmethod
    def on_key_redo(self):
        ...

    @abc.abstractmethod
    def on_cells_selection_press(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        ...

    @abc.abstractmethod
    def on_cells_selection_double(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        ...

    @abc.abstractmethod
    def on_cells_selection_motion(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        ...

    @abc.abstractmethod
    def on_cells_selection_release(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        ...

    @abc.abstractmethod
    def on_chars_selection_press(
        self,
        char_x: CellCoord,
        char_y: CellCoord,
    ):
        ...

    @abc.abstractmethod
    def on_chars_selection_double(
        self,
        char_x: CellCoord,
        char_y: CellCoord,
    ):
        ...

    @abc.abstractmethod
    def on_chars_selection_motion(
        self,
        char_x: CellCoord,
        char_y: CellCoord,
    ):
        ...

    @abc.abstractmethod
    def on_chars_selection_release(
        self,
        char_x: CellCoord,
        char_y: CellCoord,
    ):
        ...


# ---------------------------------------------------------------------------------------------------------------------

class BaseEngine(
    EngineFileCallbacks,
    EngineEditCallbacks,
    EngineViewCallbacks,
    EngineNavigationCallbacks,
    EngineHelpCallbacks,
    EngineSetCallbacks,
    EngineEditorCallbacks,
):

    def __init__(
        self,
        ui: 'BaseUserInterface' = None,
        status: Optional[EngineStatus] = None,
    ):
        if status is None:
            status = EngineStatus()

        self.ui: 'BaseUserInterface' = ui
        self.status: EngineStatus = status

    @abc.abstractmethod
    def escape_selection(self) -> None:
        ...

    @abc.abstractmethod
    def select_homogeneous(self, address: Address) -> Tuple[Address, Address, Optional[Value]]:
        ...

    @abc.abstractmethod
    def select_range(self, start: Address, endex: Address) -> Tuple[Address, Address]:
        ...

    @abc.abstractmethod
    def select_all(self) -> Tuple[Address, Address]:
        ...

    @abc.abstractmethod
    def switch_selection_mode(self) -> SelectionMode:
        ...

    @abc.abstractmethod
    def shift_memory(self, offset: Address) -> None:
        ...

    @abc.abstractmethod
    def shift_selection(self, offset: Address) -> None:
        ...

    @abc.abstractmethod
    def write_digit(self, digit_char: str, insert: bool = False) -> bool:
        ...

    @abc.abstractmethod
    def write_byte(self, value: int, insert: bool = False) -> bool:
        ...

    @abc.abstractmethod
    def reserve_cell(self) -> None:
        ...

    @abc.abstractmethod
    def clear_cell(self) -> None:
        ...

    @abc.abstractmethod
    def delete_cell(self) -> None:
        ...

    @abc.abstractmethod
    def clear_selection(self) -> None:
        ...

    @abc.abstractmethod
    def delete_selection(self) -> None:
        ...

    @abc.abstractmethod
    def crop_selection(self) -> None:
        ...

    @abc.abstractmethod
    def cut_selection(self) -> None:
        ...

    @abc.abstractmethod
    def copy_selection(self) -> None:
        ...

    @abc.abstractmethod
    def paste_selection(self, clear: bool = False) -> None:
        ...

    @abc.abstractmethod
    def fill_selection(self, value: int):
        ...

    @abc.abstractmethod
    def flood_selection(self, value: int):
        ...

    @abc.abstractmethod
    def reserve_selection(self):
        ...

    @abc.abstractmethod
    def copy_cursor_address(self) -> str:
        ...

    @abc.abstractmethod
    def switch_cursor_mode(self) -> CursorMode:
        ...

    @abc.abstractmethod
    def set_cursor_cell(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
        digit: CellCoord,
    ) -> None:
        ...

    @abc.abstractmethod
    def goto_memory_absolute(self, address: Address, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def goto_memory_relative(self, delta: Address, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def goto_memory_start(self, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def goto_memory_endin(self, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def goto_memory_endex(self, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def goto_line_start(self, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def goto_line_endin(self, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def goto_line_endex(self, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def goto_block_start(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def goto_block_endin(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def goto_block_previous(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def goto_block_next(self, selecting: bool = False):
        ...

    @abc.abstractmethod
    def move_up(self, delta_y: CellCoord = 1, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def move_down(self, delta_y: CellCoord = 1, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def move_page_up(self, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def move_page_down(self, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def move_left(self, whole_byte: bool = True, selecting: bool = False) -> None:
        ...

    @abc.abstractmethod
    def move_right(self, whole_byte: bool = True, selecting: bool = False) -> None:
        ...


# ---------------------------------------------------------------------------------------------------------------------

class BaseMemento(abc.ABC):

    def __init__(
        self,
        engine: BaseEngine,
        status: EngineStatus,
    ):
        self._engine: BaseEngine = engine
        self._status: EngineStatus = status

    @abc.abstractmethod
    def redo(self) -> None:
        ...

    @abc.abstractmethod
    def undo(self) -> None:
        ...


# =====================================================================================================================

class BaseEditorWidget(abc.ABC):

    def __init__(self):
        self._address_start: Address = 0  # dummy
        self._address_endex: Address = 0  # dummy

        self._cell_start: CellCoords = (0, 0)  # dummy
        self._cell_endex: CellCoords = (1, 1)  # dummy

        self._chars_visible: bool = True

    @property
    def view_start_address(self) -> Address:
        return self._address_start

    @property
    def view_end_address(self) -> Address:
        return max(self._address_start, self._address_endex - 1)

    @property
    def view_size_address(self) -> Address:
        return self._address_endex - self._address_start

    @property
    def view_start_cell(self) -> CellCoords:
        return self._cell_start

    @property
    def view_end_cell(self) -> CellCoords:
        endex_x, endex_y = self._cell_endex
        return (endex_x - 1), (endex_y - 1)

    @property
    def view_size_cell(self) -> CellCoords:
        start_x, start_y = self._cell_start
        endex_x, endex_y = self._cell_endex
        return (endex_x - start_x), (endex_y - start_y)

    @property
    def chars_visible(self) -> bool:
        return self._chars_visible

    @chars_visible.setter
    def chars_visible(self, visible: bool) -> None:
        visible = bool(visible)

        if self._chars_visible < visible:
            self._chars_visible = visible
            self.redraw()

        elif self._chars_visible > visible:
            self._chars_visible = visible
            self.redraw()

    @abc.abstractmethod
    def focus_set(self):
        ...

    @abc.abstractmethod
    def focus_set_cells(self):
        ...

    @abc.abstractmethod
    def focus_set_chars(self):
        ...

    @abc.abstractmethod
    def get_half_page_height(self) -> CellCoord:
        ...

    @abc.abstractmethod
    def get_cell_bounds_y(self) -> Tuple[CellCoord, CellCoord]:
        ...

    @abc.abstractmethod
    def mark_dirty_cell(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
    ) -> None:
        ...

    @abc.abstractmethod
    def mark_dirty_all(self) -> None:
        ...

    @abc.abstractmethod
    def mark_dirty_inline(
        self,
        start_x: Optional[CellCoord] = None,
        start_y: Optional[CellCoord] = None,
        endin_x: Optional[CellCoord] = None,
        endin_y: Optional[CellCoord] = None,
    ) -> None:
        ...

    @abc.abstractmethod
    def mark_dirty_range(
        self,
        start_address: Optional[Address] = None,
        endex_address: Optional[Address] = None,
    ) -> None:
        ...

    @abc.abstractmethod
    def update_vbar(self) -> None:
        ...

    @abc.abstractmethod
    def update_view(
        self,
        force_geometry: bool = False,
        force_selection: bool = False,
        force_content: bool = False,
    ) -> None:
        ...

    @abc.abstractmethod
    def update_cursor(self) -> None:
        ...

    @abc.abstractmethod
    def redraw(self) -> None:
        ...

    @abc.abstractmethod
    def scroll_up(self, delta_y: int = 1) -> None:
        ...

    @abc.abstractmethod
    def scroll_down(self, delta_y: int = 1) -> None:
        ...

    @abc.abstractmethod
    def scroll_page_up(self) -> None:
        ...

    @abc.abstractmethod
    def scroll_page_down(self) -> None:
        ...

    @abc.abstractmethod
    def scroll_top(self, delta_y: CellCoord = 0) -> None:
        ...

    @abc.abstractmethod
    def scroll_bottom(self, delta_y: CellCoord = 0) -> None:
        ...

    @abc.abstractmethod
    def ask_big_selection(self, size: Address) -> bool:
        ...


# ---------------------------------------------------------------------------------------------------------------------

class BaseUserInterface(abc.ABC):

    def __init__(
        self,
        manager: 'BaseInstanceManager',
    ):
        self._manager: 'BaseInstanceManager' = manager
        self._manager_key: int = manager.add(self)
        self.editor: Optional[BaseEditorWidget] = None

    def quit(self) -> None:
        self._manager.remove(self._manager_key)

    def create_new(self) -> 'BaseUserInterface':
        cls = type(self)
        ui = cls(self._manager)
        return ui

    @abc.abstractmethod
    def update_status(self) -> None:
        ...

    @abc.abstractmethod
    def get_start_text(self) -> str:
        ...

    @abc.abstractmethod
    def set_start_text(self, text: str, focus: bool = False) -> None:
        ...

    @abc.abstractmethod
    def focus_start_text(self) -> None:
        ...

    @abc.abstractmethod
    def get_start_address(self) -> Address:
        ...

    @abc.abstractmethod
    def set_start_address(self, address: Address) -> None:
        ...

    @abc.abstractmethod
    def get_endin_text(self) -> str:
        ...

    @abc.abstractmethod
    def set_endin_text(self, text: str, focus: bool = False) -> None:
        ...

    @abc.abstractmethod
    def focus_endin_text(self) -> None:
        ...

    @abc.abstractmethod
    def get_endin_address(self) -> Address:
        ...

    @abc.abstractmethod
    def set_endin_address(self, address: Address) -> None:
        ...

    @abc.abstractmethod
    def show_about(self) -> None:
        ...

    @abc.abstractmethod
    def show_info(self, title: str, message: str) -> None:
        ...

    @abc.abstractmethod
    def show_warning(self, title: str, message: str) -> None:
        ...

    @abc.abstractmethod
    def show_error(self, title: str, message: str) -> None:
        ...

    @abc.abstractmethod
    def ask_open_file_path(self) -> Optional[str]:
        ...

    @abc.abstractmethod
    def ask_save_file_path(self) -> Optional[str]:
        ...

    @abc.abstractmethod
    def ask_line_length_custom(self) -> Optional[int]:
        ...

    @abc.abstractmethod
    def ask_address_bits_custom(self) -> Optional[int]:
        ...

    @abc.abstractmethod
    def ask_address_skip_custom(self) -> Optional[int]:
        ...

    @abc.abstractmethod
    def ask_chars_encoding_custom(self) -> Optional[int]:
        ...

    @abc.abstractmethod
    def update_title_by_file_path(self) -> None:
        ...

    @abc.abstractmethod
    def update_menus_by_selection(self) -> None:
        ...

    @abc.abstractmethod
    def update_menus_by_cursor(self) -> None:
        ...


# =====================================================================================================================

class BaseInstanceManager:

    def __init__(self):
        self._counter: InstanceIndex = 0
        self._instances: MutableMapping[InstanceIndex, BaseUserInterface] = {}

    def __len__(self) -> int:
        return len(self._instances)

    def __bool__(self) -> bool:
        return bool(self._instances)

    def add(self, instance: BaseUserInterface) -> InstanceIndex:
        key = self._counter
        self._instances[key] = instance
        self._counter += 1
        return key

    def remove(self, index: InstanceIndex) -> BaseUserInterface:
        instance = self._instances.pop(index)
        return instance

    def run(self) -> None:
        pass

    def quit(self) -> None:
        while self._instances:
            _, instance = self._instances.popitem()
            instance.quit()
