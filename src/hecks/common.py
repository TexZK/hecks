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

import enum
import tkinter as tk
from math import floor
from typing import MutableMapping
from typing import Optional
from typing import Tuple

from bytesparse._py import Address
from bytesparse._py import Memory
from bytesparse._py import Value

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

BYTE_ENCODINGS = (
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
)


def build_encoding_table(encoding: str, nonprintable: str = '.') -> Tuple[str]:
    lut = []
    for i in range(256):
        try:
            t = bytes([i]).decode(encoding=encoding)
        except UnicodeError:
            t = nonprintable
        lut.append(t if t.isprintable() else nonprintable)
    lut = tuple(lut)
    return lut


# =====================================================================================================================

class EngineStatus:

    def __init__(self):
        # File properties
        self.file_path: Optional[str] = None

        # Initialize memory
        # XXX FIXME: allocate some dummy data for debug
        data = bytes(range(256)) * 8
        self.memory = Memory(data=data, offset=0xDA7A0000)

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

class EngineFileCallbacks:

    def on_file_new(self: 'EngineFileCallbacks') -> None:
        raise NotImplementedError

    def on_file_open(self: 'EngineFileCallbacks') -> None:
        raise NotImplementedError

    def on_file_import(self: 'EngineFileCallbacks') -> None:
        raise NotImplementedError

    def on_file_save(self: 'EngineFileCallbacks') -> None:
        raise NotImplementedError

    def on_file_save_as(self: 'EngineFileCallbacks') -> None:
        raise NotImplementedError

    def on_file_settings(self: 'EngineFileCallbacks') -> None:
        raise NotImplementedError

    def on_file_exit(self: 'EngineFileCallbacks') -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------------------------------------------------

class EngineEditCallbacks:

    def on_edit_undo(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_redo(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_cut(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_copy(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_paste(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_delete(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_cursor_mode(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_clear(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_reserve(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_fill(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_flood(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_crop(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_move_focus(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_move_apply(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_export(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_select_all(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_select_range(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_copy_address(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError

    def on_edit_find(self: 'EngineEditCallbacks') -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------------------------------------------------

class EngineViewCallbacks:

    def on_view_line_length_custom(self: 'EngineViewCallbacks') -> None:
        raise NotImplementedError

    def on_view_address_bits_custom(self: 'EngineViewCallbacks') -> None:
        raise NotImplementedError

    def on_view_chars_encoding_custom(self: 'EngineViewCallbacks') -> None:
        raise NotImplementedError

    def on_view_redraw(self: 'EngineViewCallbacks') -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------------------------------------------------

class EngineNavigationCallbacks:

    def on_nav_editor_focus(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_memory_address_start_focus(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_memory_address_start_apply(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_memory_address_endin_focus(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_memory_address_endin_apply(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_memory_address_copy(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_memory_start(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_memory_endin(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_memory_endex(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_address_skip(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_block_previous(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_block_next(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_block_start(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_block_endin(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_byte_previous(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_byte_next(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_line_start(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_goto_line_endin(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_scroll_line_up(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_scroll_line_down(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_scroll_page_up(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_scroll_page_down(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_scroll_top(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError

    def on_nav_scroll_bottom(self: 'EngineNavigationCallbacks') -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------------------------------------------------

class EngineHelpCallbacks:

    def on_help_about(self: 'EngineHelpCallbacks') -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------------------------------------------------

class EngineSetCallbacks:

    def on_set_chars_visible(self: 'EngineSetCallbacks', visible: bool) -> None:
        raise NotImplementedError

    def on_set_line_length(self: 'EngineSetCallbacks', line_length: CellCoord) -> None:
        raise NotImplementedError

    def on_set_chars_encoding(self: 'EngineSetCallbacks', encoding: str) -> None:
        raise NotImplementedError

    def on_set_cell_mode(self: 'EngineSetCallbacks', mode: ValueFormatEnum) -> None:
        raise NotImplementedError

    def on_set_cell_prefix(self: 'EngineSetCallbacks', prefix: bool) -> None:
        raise NotImplementedError

    def on_set_cell_suffix(self: 'EngineSetCallbacks', suffix: bool) -> None:
        raise NotImplementedError

    def on_set_cell_zeroed(self: 'EngineSetCallbacks', zeroed: bool) -> None:
        raise NotImplementedError

    def on_set_address_mode(self: 'EngineSetCallbacks', mode: ValueFormatEnum) -> None:
        raise NotImplementedError

    def on_set_address_prefix(self: 'EngineSetCallbacks', prefix: bool) -> None:
        raise NotImplementedError

    def on_set_address_suffix(self: 'EngineSetCallbacks', suffix: bool) -> None:
        raise NotImplementedError

    def on_set_address_zeroed(self: 'EngineSetCallbacks', zeroed: bool) -> None:
        raise NotImplementedError

    def on_set_address_skip(self: 'EngineSetCallbacks', skip: Address) -> None:
        raise NotImplementedError

    def on_set_address_bits(self: 'EngineSetCallbacks', bitsize: int) -> None:
        raise NotImplementedError

    def on_set_offset_mode(self: 'EngineSetCallbacks', mode: ValueFormatEnum) -> None:
        raise NotImplementedError

    def on_set_offset_prefix(self: 'EngineSetCallbacks', prefix: bool) -> None:
        raise NotImplementedError

    def on_set_offset_suffix(self: 'EngineSetCallbacks', suffix: bool) -> None:
        raise NotImplementedError

    def on_set_offset_zeroed(self: 'EngineSetCallbacks', zeroed: bool) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------------------------------------------------

class EngineEditorCallbacks:

    def on_key_digit_cells(self: 'EngineEditorCallbacks', digit: Value):
        raise NotImplementedError

    def on_key_digit_chars(self: 'EngineEditorCallbacks', digit: Value):
        raise NotImplementedError

    def on_key_reserve_cell(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_delete_cell(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_clear_cell(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_clear_back(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_clear_next(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_delete(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_fill(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_flood(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_cut(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_copy(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_paste(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_crop(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_move_focus(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_move_apply(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_scroll_line_up(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_scroll_page_up(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_scroll_line_down(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_scroll_page_down(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_scroll_top(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_scroll_bottom(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_move_left_digit(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_move_right_digit(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_move_left_byte(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_move_right_byte(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_move_line_up(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_move_page_up(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_move_line_down(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_move_page_down(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_goto_line_start(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_goto_line_endin(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_goto_memory_apply(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_goto_memory_focus(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_goto_memory_start(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_goto_memory_endin(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_goto_memory_endex(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_goto_block_previous(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_goto_block_next(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_goto_block_start(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_goto_block_endin(self: 'EngineEditorCallbacks', selecting: bool = False):
        raise NotImplementedError

    def on_key_copy_address(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_set_address(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_select_all(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_select_range(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_escape_selection(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_switch_cursor_mode(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_redraw(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_undo(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_key_redo(self: 'EngineEditorCallbacks'):
        raise NotImplementedError

    def on_cells_selection_press(
        self: 'EngineEditorCallbacks',
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        raise NotImplementedError

    def on_cells_selection_double(
        self: 'EngineEditorCallbacks',
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        raise NotImplementedError

    def on_cells_selection_motion(
        self: 'EngineEditorCallbacks',
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        raise NotImplementedError

    def on_cells_selection_release(
        self: 'EngineEditorCallbacks',
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        raise NotImplementedError

    def on_chars_selection_press(
        self: 'EngineEditorCallbacks',
        char_x: CellCoord,
        char_y: CellCoord,
    ):
        raise NotImplementedError

    def on_chars_selection_double(
        self: 'EngineEditorCallbacks',
        char_x: CellCoord,
        char_y: CellCoord,
    ):
        raise NotImplementedError

    def on_chars_selection_motion(
        self: 'EngineEditorCallbacks',
        char_x: CellCoord,
        char_y: CellCoord,
    ):
        raise NotImplementedError

    def on_chars_selection_release(
        self: 'EngineEditorCallbacks',
        char_x: CellCoord,
        char_y: CellCoord,
    ):
        raise NotImplementedError


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
        self: 'BaseEngine',
        ui: 'BaseUserInterface' = None,
        status: Optional[EngineStatus] = None,
    ):
        if status is None:
            status = EngineStatus()

        self.ui: 'BaseUserInterface' = ui
        self.status: EngineStatus = status

    def escape_selection(self) -> None:
        raise NotImplementedError

    def select_homogeneous(self, address: Address) -> Tuple[Address, Address, Optional[Value]]:
        raise NotImplementedError

    def select_range(self, start: Address, endex: Address) -> Tuple[Address, Address]:
        raise NotImplementedError

    def select_all(self) -> Tuple[Address, Address]:
        raise NotImplementedError

    def switch_selection_mode(self) -> SelectionMode:
        raise NotImplementedError

    def shift_memory(self, offset: Address) -> None:
        raise NotImplementedError

    def shift_selection(self, offset: Address) -> None:
        raise NotImplementedError

    def write_digit(self, digit_char: str, insert: bool = False) -> bool:
        raise NotImplementedError

    def write_byte(self, value: int, insert: bool = False) -> bool:
        raise NotImplementedError

    def reserve_cell(self) -> None:
        raise NotImplementedError

    def clear_cell(self) -> None:
        raise NotImplementedError

    def delete_cell(self) -> None:
        raise NotImplementedError

    def clear_selection(self) -> None:
        raise NotImplementedError

    def delete_selection(self) -> None:
        raise NotImplementedError

    def crop_selection(self) -> None:
        raise NotImplementedError

    def cut_selection(self) -> None:
        raise NotImplementedError

    def copy_selection(self) -> None:
        raise NotImplementedError

    def paste_selection(self, clear: bool = False) -> None:
        raise NotImplementedError

    def fill_selection(self, value: int):
        raise NotImplementedError

    def flood_selection(self, value: int):
        raise NotImplementedError

    def reserve_selection(self):
        raise NotImplementedError

    def copy_cursor_address(self) -> str:
        raise NotImplementedError

    def switch_cursor_mode(self) -> CursorMode:
        raise NotImplementedError

    def set_cursor_cell(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
        digit: CellCoord,
    ) -> None:
        raise NotImplementedError

    def goto_memory_absolute(self, address: Address, selecting: bool = False) -> None:
        raise NotImplementedError

    def goto_memory_relative(self, delta: Address, selecting: bool = False) -> None:
        raise NotImplementedError

    def goto_memory_start(self, selecting: bool = False) -> None:
        raise NotImplementedError

    def goto_memory_endin(self, selecting: bool = False) -> None:
        raise NotImplementedError

    def goto_memory_endex(self, selecting: bool = False) -> None:
        raise NotImplementedError

    def goto_line_start(self, selecting: bool = False) -> None:
        raise NotImplementedError

    def goto_line_endin(self, selecting: bool = False) -> None:
        raise NotImplementedError

    def goto_line_endex(self, selecting: bool = False) -> None:
        raise NotImplementedError

    def goto_block_start(self, selecting: bool = False):
        raise NotImplementedError

    def goto_block_endin(self, selecting: bool = False):
        raise NotImplementedError

    def goto_block_previous(self, selecting: bool = False):
        raise NotImplementedError

    def goto_block_next(self, selecting: bool = False):
        raise NotImplementedError

    def move_up(self, delta_y: CellCoord = 1, selecting: bool = False) -> None:
        raise NotImplementedError

    def move_down(self, delta_y: CellCoord = 1, selecting: bool = False) -> None:
        raise NotImplementedError

    def move_page_up(self, selecting: bool = False) -> None:
        raise NotImplementedError

    def move_page_down(self, selecting: bool = False) -> None:
        raise NotImplementedError

    def move_left(self, whole_byte: bool = True, selecting: bool = False) -> None:
        raise NotImplementedError

    def move_right(self, whole_byte: bool = True, selecting: bool = False) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------------------------------------------------

class BaseMemento:

    def __init__(
        self: 'BaseMemento',
        engine: BaseEngine,
        status: EngineStatus,
    ):
        self._engine: BaseEngine = engine
        self._status: EngineStatus = status

    def redo(self: 'BaseMemento') -> None:
        raise NotImplementedError

    def undo(self: 'BaseMemento') -> None:
        raise NotImplementedError


# =====================================================================================================================

class BaseEditorWidget:

    def __init__(self: 'BaseEditorWidget'):
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

    def focus_set(self):
        raise NotImplementedError

    def get_half_page_height(self) -> CellCoord:
        raise NotImplementedError

    def get_cell_bounds_y(self) -> Tuple[CellCoord, CellCoord]:
        raise NotImplementedError

    def mark_dirty_cell(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
    ):
        raise NotImplementedError

    def mark_dirty_all(self):
        raise NotImplementedError

    def mark_dirty_inline(
        self,
        start_x: Optional[CellCoord] = None,
        start_y: Optional[CellCoord] = None,
        endin_x: Optional[CellCoord] = None,
        endin_y: Optional[CellCoord] = None,
    ):
        raise NotImplementedError

    def mark_dirty_range(
        self,
        start_address: Optional[Address] = None,
        endex_address: Optional[Address] = None,
    ):
        raise NotImplementedError

    def update_vbar(self):
        raise NotImplementedError

    def update_view(
        self,
        force_geometry: bool = False,
        force_selection: bool = False,
        force_content: bool = False,
    ):
        raise NotImplementedError

    def update_cursor(self):
        raise NotImplementedError

    def redraw(self):
        raise NotImplementedError

    def scroll_up(self, delta_y: int = 1) -> None:
        raise NotImplementedError

    def scroll_down(self, delta_y: int = 1) -> None:
        raise NotImplementedError

    def scroll_page_up(self) -> None:
        raise NotImplementedError

    def scroll_page_down(self) -> None:
        raise NotImplementedError

    def scroll_top(self, delta_y: CellCoord = 0) -> None:
        raise NotImplementedError

    def scroll_bottom(self, delta_y: CellCoord = 0) -> None:
        raise NotImplementedError

    def ask_big_selection(self, size: Address) -> bool:
        raise NotImplementedError


# ---------------------------------------------------------------------------------------------------------------------

class BaseUserInterface:

    def __init__(
        self: 'BaseUserInterface',
        manager: 'BaseInstanceManager',
    ):
        self._manager: 'BaseInstanceManager' = manager
        self._manager_key: int = manager.add(self)
        self.editor: Optional[BaseEditorWidget] = None

    def quit(self):
        self._manager.remove(self._manager_key)

    def create_new(self) -> 'BaseUserInterface':
        cls = type(self)
        ui = cls(self._manager)
        return ui

    def update_status(self):
        raise NotImplementedError

    def get_start_text(self) -> str:
        raise NotImplementedError

    def set_start_text(self, text: str, focus: bool = False) -> None:
        raise NotImplementedError

    def focus_start_text(self) -> None:
        raise NotImplementedError

    def get_start_address(self) -> Address:
        raise NotImplementedError

    def set_start_address(self, address: Address) -> None:
        raise NotImplementedError

    def get_endin_text(self) -> str:
        raise NotImplementedError

    def set_endin_text(self, text: str, focus: bool = False) -> None:
        raise NotImplementedError

    def focus_endin_text(self) -> None:
        raise NotImplementedError

    def get_endin_address(self) -> Address:
        raise NotImplementedError

    def set_endin_address(self, address: Address) -> None:
        raise NotImplementedError

    def show_about(self):
        raise NotImplementedError

    def show_info(self, title: str, message: str):
        raise NotImplementedError

    def show_warning(self, title: str, message: str):
        raise NotImplementedError

    def show_error(self, title: str, message: str):
        raise NotImplementedError

    def ask_open_file_path(self) -> Optional[str]:
        raise NotImplementedError

    def ask_save_file_path(self) -> Optional[str]:
        raise NotImplementedError

    def ask_line_length_custom(self) -> Optional[int]:
        raise NotImplementedError

    def ask_address_bits_custom(self) -> Optional[int]:
        raise NotImplementedError

    def ask_address_skip_custom(self) -> Optional[int]:
        raise NotImplementedError

    def ask_chars_encoding_custom(self) -> Optional[int]:
        raise NotImplementedError

    def update_title_by_file_path(self):
        raise NotImplementedError

    def update_menus_by_selection(self):
        raise NotImplementedError

    def update_menus_by_cursor(self):
        raise NotImplementedError


# =====================================================================================================================

class BaseInstanceManager:

    def __init__(self):
        self._counter: int = 0
        self._instances: MutableMapping[int, BaseUserInterface] = {}

    def __len__(self) -> int:
        return len(self._instances)

    def __bool__(self) -> bool:
        return bool(self._instances)

    def add(self, instance: BaseUserInterface) -> int:
        key = self._counter
        self._instances[key] = instance
        self._counter += 1
        return key

    def remove(self, key: int) -> object:
        instance = self._instances.pop(key)
        return instance

    def run(self) -> None:
        pass

    def quit(self) -> None:
        for instance in list(self._instances.values()):
            instance.quit()
        self._instances.clear()
