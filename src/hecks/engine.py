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

import inspect
import tkinter.filedialog
import tkinter.font
import tkinter.messagebox
import tkinter.simpledialog
from math import floor
from typing import Callable
from typing import Optional
from typing import Tuple
from typing import cast as _cast

from bytesparse.base import Address
from bytesparse.base import Value
from bytesparse.inplace import Memory
import hexrec.blocks as _hb
import hexrec.records as _hr
import pyperclip

from .common import BIG_SELECTION_SIZE
from .common import BaseEngine
from .common import BaseUserInterface
from .common import CellCoord
from .common import CharCoord
from .common import CursorMode
from .common import EngineStatus
from .common import SelectionMode
from .common import build_encoding_table
from .utils import VALUE_FORMAT_INTEGER_BASE
from .utils import ValueFormatEnum
from .utils import memory_to_clipboard
from .utils import clipboard_to_memory
from .utils import iter_lines
from .utils import parse_int


def _todo():  # TODO remove all of its calls
    print(f'TODO: {inspect.stack()[1].function}')


# =====================================================================================================================

class Engine(BaseEngine):

    def __init__(
        self,
        ui: BaseUserInterface = None,
        status: Optional[EngineStatus] = None,
    ):
        super().__init__(ui, status)

    def _set_selection_start(self, cell_x: CellCoord, cell_y: CellCoord) -> None:
        status = self.status
        status.sel_start_cell = (cell_x, cell_y)
        status.sel_start_address = status.cell_coords_to_address(cell_x, cell_y)

    def _set_selection_endin(self, cell_x: CellCoord, cell_y: CellCoord) -> None:
        status = self.status
        status.sel_endin_cell = (cell_x, cell_y)
        status.sel_endin_address = status.cell_coords_to_address(cell_x, cell_y)

    def _update_selection(self, selecting: bool) -> None:
        widget = self.ui.editor
        status = self.status
        if selecting:
            if not status.sel_mode:
                status.sel_mode = SelectionMode.NORMAL
                self.ui.update_menus_by_selection()

            self._set_selection_endin(*status.cursor_cell)
            widget.update_view(force_selection=True)
        else:
            self.escape_selection()

    def escape_selection(self) -> None:
        widget = self.ui.editor
        status = self.status

        cell_x, cell_y = status.cursor_cell
        self._set_selection_start(cell_x, cell_y)
        self._set_selection_endin(cell_x, cell_y)

        if status.sel_mode:
            status.sel_mode = SelectionMode.OFF
            widget.update_view(force_selection=True)
            self.ui.update_menus_by_selection()

    def select_homogeneous(self, address: Address) -> Tuple[Address, Address, Optional[Value]]:  # TODO: add menu command
        widget = self.ui.editor
        status = self.status
        start, endex, value = status.memory.equal_span(address)

        if start is not None and endex is not None and start < endex:
            status.sel_mode = SelectionMode.NORMAL
            self._set_selection_start(*status.address_to_cell_coords(start))
            self._set_selection_endin(*status.address_to_cell_coords(endex - 1))
            widget.update_view(force_selection=True)
            self.ui.update_menus_by_selection()

        return start, endex, value

    def select_range(self, start: Address, endex: Address) -> Tuple[Address, Address]:
        widget = self.ui.editor
        status = self.status

        if endex == start:
            self.escape_selection()
        else:
            if endex < start:
                endex, start = start, endex

            if not status.sel_mode:
                status.sel_mode = SelectionMode.NORMAL
                self.ui.update_menus_by_selection()

            cell_start = status.address_to_cell_coords(start)
            cell_endin = status.address_to_cell_coords(endex - 1)
            self._set_selection_start(*cell_start)
            self._set_selection_endin(*cell_endin)
            self.set_cursor_cell(*cell_start, 0)
            widget.update_view(force_selection=True)

        return start, endex

    def select_all(self) -> Tuple[Address, Address]:
        memory = self.status.memory
        return self.select_range(memory.start, memory.endex)

    def switch_selection_mode(self) -> SelectionMode:
        status = self.status
        if status.sel_mode == SelectionMode.NORMAL:
            status.sel_mode = SelectionMode.RECTANGLE
        elif status.sel_mode == SelectionMode.RECTANGLE:
            status.sel_mode = SelectionMode.NORMAL
        self._update_selection(bool(status.sel_mode))
        return status.sel_mode

    def shift_memory(self, offset: Address) -> None:
        self.escape_selection()

        if offset:
            memory = self.status.memory
            memory.shift(offset)

            widget = self.ui.editor
            widget.mark_dirty_all()
            widget.update_view(force_content=True)
            self.ui.update_menus_by_selection()

    def shift_selection(self, offset: Address) -> None:
        if offset:
            status = self.status
            sel_mode = status.sel_mode

            if sel_mode == SelectionMode.NORMAL:
                start = status.sel_start_address
                endex = status.sel_endin_address + 1
                origin = start

                memory = status.memory
                chunk = memory.extract(start, endex)
                memory.delete(start, endex)
                start += offset
                endex += offset
                memory.write(start, chunk)
                del chunk

                self._set_selection_start(*status.address_to_cell_coords(start))
                self._set_selection_endin(*status.address_to_cell_coords(endex - 1))

                widget = self.ui.editor
                widget.mark_dirty_range(min(start, origin))
                widget.update_view(force_content=True)
                self.ui.update_menus_by_selection()

            elif sel_mode == SelectionMode.RECTANGLE:
                pass  # TODO

    def write_digit(self, digit_char: str, insert: bool = False) -> bool:
        widget = self.ui.editor
        status = self.status
        sel_mode_prev = status.sel_mode
        self.delete_selection()

        if sel_mode_prev:
            insert = True
        elif status.cursor_mode == CursorMode.INSERT:
            if status.cursor_digit == 0:
                insert = True

        memory = status.memory
        address = status.cursor_address
        value_before = memory.peek(address)
        if insert:
            widget.mark_dirty_range(address)
            memory.poke(address, 0)
            value = 0
        else:
            widget.mark_dirty_cell(*status.cursor_cell)
            value = memory.peek(address) or 0

        try:
            cursor_digit = status.cursor_digit
            if 0 <= status.cursor_digit < status.cell_format_length:
                text = status.cell_format_string.format(value)
                text = text[:cursor_digit] + digit_char + text[cursor_digit + 1:]
                value = int(text, VALUE_FORMAT_INTEGER_BASE[status.cell_format_mode])
            else:
                raise ValueError
        except ValueError:
            return False  # just ignore

        try:
            chunk = bytes([value])
        except OverflowError:
            return False  # just ignore

        memory.write(address, chunk)
        widget.update_view(force_content=True)

        self._move_cursor_by_char(+1, 0)
        if value_before is None:
            self.ui.update_menus_by_selection()
        return True

    def write_byte(self, value: int, insert: bool = False) -> bool:
        widget = self.ui.editor
        status = self.status
        sel_mode_prev = status.sel_mode
        self.delete_selection()

        if sel_mode_prev:
            insert = True
        elif status.cursor_mode == CursorMode.INSERT:
            insert = True

        memory = status.memory
        address = status.cursor_address
        value_before = memory.peek(address)
        if insert:
            widget.mark_dirty_range(address)
            memory.poke(address, value)
        else:
            widget.mark_dirty_cell(*status.cursor_cell)
            memory.poke(address, value)
        widget.update_view(force_content=True)

        status.cursor_digit = 0
        self._move_cursor_by_char(status.cell_format_length, 0)
        if value_before is None:
            self.ui.update_menus_by_selection()
        return True

    def reserve_cell(self) -> None:
        widget = self.ui.editor
        status = self.status
        sel_mode_before = status.sel_mode
        self.reserve_selection()

        if not sel_mode_before:
            address = status.cursor_address
            status.memory.reserve(address, address + 1)
            widget.mark_dirty_range(address)
            widget.update_view(force_content=True)
            self.ui.update_menus_by_selection()

    def clear_cell(self) -> None:
        widget = self.ui.editor
        status = self.status
        sel_mode_before = status.sel_mode
        self.clear_selection()

        if not sel_mode_before:
            address = status.cursor_address
            status.memory.clear(address, address + 1)
            cell_x, cell_y = status.cursor_cell
            widget.mark_dirty_cell(cell_x, cell_y)
            widget.update_view(force_content=True)
            self.ui.update_menus_by_selection()

    def delete_cell(self) -> None:
        widget = self.ui.editor
        status = self.status
        sel_mode_before = status.sel_mode
        self.delete_selection()

        if not sel_mode_before:
            address = status.cursor_address
            status.memory.delete(address, address + 1)
            widget.mark_dirty_range(address)
            widget.update_view(force_content=True)
            self.ui.update_menus_by_selection()

    def _cleanup_selection(self, reserve: bool = False) -> None:
        widget = self.ui.editor
        status = self.status
        sel_mode = status.sel_mode

        if sel_mode:
            address_start = status.sel_start_address
            address_endin = status.sel_endin_address
            cell_start = status.sel_start_cell
            cell_endin = status.sel_endin_cell

            if address_endin < address_start:
                address_endin, address_start = address_start, address_endin
                cell_endin, cell_start = cell_start, cell_endin

            address_endex = address_endin + 1
            operate = status.memory.clear if reserve else status.memory.delete
            operate = _cast(Callable, operate)
            widget.mark_dirty_range(address_start)

            if sel_mode == SelectionMode.NORMAL:
                operate(address_start, address_endex)
                widget.update_view(force_content=True)

            elif sel_mode == SelectionMode.RECTANGLE:
                line_length = status.line_length
                cell_w = cell_endin[0] + 1 - cell_start[0]

                while address_endex > address_start:
                    operate(address_endex - cell_w, address_endex)
                    address_endex -= line_length

                widget.update_view(force_content=True)

            self.set_cursor_cell(*cell_start, 0)

        self.escape_selection()

    def clear_selection(self) -> None:
        self._cleanup_selection(reserve=True)

    def delete_selection(self) -> None:
        self._cleanup_selection(reserve=False)

    def crop_selection(self) -> None:
        widget = self.ui.editor
        status = self.status
        sel_mode = status.sel_mode

        if sel_mode == SelectionMode.NORMAL:
            start = status.sel_start_address
            endin = status.sel_endin_address
            if endin < start:
                start, endin = endin, start
            status.memory.crop(start, endin + 1)
            widget.mark_dirty_all()
            widget.update_view(force_content=True)
            self.goto_memory_absolute(start)

        elif sel_mode == SelectionMode.RECTANGLE:
            pass  # TODO

    def cut_selection(self) -> None:
        self.copy_selection()
        self.delete_selection()

    def copy_selection(self) -> None:
        widget = self.ui.editor
        status = self.status
        sel_mode = status.sel_mode

        if sel_mode == SelectionMode.NORMAL:
            address_start = status.sel_start_address
            address_endin = status.sel_endin_address
            if address_endin < address_start:
                address_start, address_endin = address_endin, address_start

            answer = True
            size = (address_endin + 1) - address_start
            if size > BIG_SELECTION_SIZE:
                answer = widget.ask_big_selection(size)

            if answer:
                extracted = status.memory.extract(address_start, address_endin + 1)
                clipboard = memory_to_clipboard(extracted)
                del extracted
                pyperclip.copy(clipboard)
                del clipboard

        elif sel_mode == SelectionMode.RECTANGLE:
            pass  # TODO

    def paste_selection(self, clear: bool = False) -> None:
        widget = self.ui.editor
        status = self.status

        self.delete_selection()

        clipboard = pyperclip.paste()
        address = status.cursor_address
        try:
            memory = clipboard_to_memory(iter_lines(clipboard))
        except ValueError:
            pass  # just ignore
        else:
            del clipboard
            start = memory.start
            endex = memory.endex
            blocks = memory._blocks

            target_start = address
            target_endex = address + endex - start

            if clear:
                status.memory.clear(target_start, target_endex)
                widget.mark_dirty_range(target_start, target_endex)

            if blocks:
                for block_start, block_data in blocks:
                    target_address = address + block_start - start
                    status.memory.write(target_address, block_data)
                    widget.mark_dirty_range(address, address + len(block_data))

            self.goto_memory_absolute(target_endex)
            widget.update_view(force_content=True)
            self.ui.update_menus_by_selection()

    def fill_selection(self, value: int):
        widget = self.ui.editor
        status = self.status
        sel_mode = status.sel_mode

        if not sel_mode:
            start, endex, _ = status.memory.equal_span(status.cursor_address)

            if start is not None and endex is not None and start < endex:
                status.memory.fill(start, endex, value)
                widget.mark_dirty_range(start, endex)

                status.sel_mode = SelectionMode.NORMAL
                self._set_selection_start(*status.address_to_cell_coords(start))
                self._set_selection_endin(*status.address_to_cell_coords(endex - 1))

        elif sel_mode == SelectionMode.NORMAL:
            start = status.sel_start_address
            endin = status.sel_endin_address
            if endin < start:
                start, endin = endin, start
            endex = endin + 1
            status.memory.fill(start, endex, value)
            widget.mark_dirty_range(start, endex)

        elif sel_mode == SelectionMode.RECTANGLE:
            pass  # TODO

        widget.update_view(force_selection=True, force_content=True)
        self.ui.update_menus_by_selection()

    def flood_selection(self, value: int):
        widget = self.ui.editor
        status = self.status
        sel_mode = status.sel_mode

        if not sel_mode:
            if status.memory.peek(status.cursor_address) is None:
                self.fill_selection(value)
            return

        elif sel_mode == SelectionMode.NORMAL:
            start = status.sel_start_address
            endin = status.sel_endin_address
            if endin < start:
                start, endin = endin, start
            endex = endin + 1
            status.memory.flood(start, endex, value)
            widget.mark_dirty_range(start, endex)

        elif sel_mode == SelectionMode.RECTANGLE:
            pass  # TODO

        widget.update_view(force_selection=True, force_content=True)
        self.ui.update_menus_by_selection()

    def reserve_selection(self):
        widget = self.ui.editor
        status = self.status
        sel_mode = status.sel_mode

        if sel_mode == SelectionMode.NORMAL:
            start = status.sel_start_address
            endin = status.sel_endin_address
            if endin < start:
                start, endin = endin, start
            status.memory.reserve(start, endin + 1 - start)
            widget.mark_dirty_range(start)
            widget.update_view(force_content=True)
            self.goto_memory_absolute(start)

        elif sel_mode == SelectionMode.RECTANGLE:
            pass  # TODO

    def copy_cursor_address(self) -> str:
        status = self.status
        address = status.cursor_address
        text = status.address_format_string.format(address)
        pyperclip.copy(text)
        return text

    def switch_cursor_mode(self) -> CursorMode:
        widget = self.ui.editor
        status = self.status
        if status.cursor_mode == CursorMode.OVERWRITE:
            status.cursor_mode = CursorMode.INSERT
        else:
            status.cursor_mode = CursorMode.OVERWRITE
        widget.update_cursor()
        return status.cursor_mode

    def set_cursor_cell(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
        digit: CellCoord,
    ) -> None:
        widget = self.ui.editor
        status = self.status

        status.cursor_cell = (cell_x, cell_y)
        status.cursor_digit = digit

        address_before = status.cursor_address
        address_after = status.cell_coords_to_address(cell_x, cell_y)
        status.cursor_address = address_after

        memory = status.memory
        address_start = memory.start
        address_endex = memory.endex

        if (address_start <= address_before < address_endex) != (address_start <= address_after < address_endex):
            self.ui.update_menus_by_cursor()

        elif (memory.peek(address_before) is None) != (memory.peek(address_after) is None):
            self.ui.update_menus_by_cursor()

        cell_start_y, cell_endex_y = widget.get_cell_bounds_y()

        if cell_y <= cell_start_y:
            widget.scroll_top()
            widget.update_vbar()

        elif cell_y >= cell_endex_y:
            widget.scroll_bottom()
            widget.update_vbar()

        else:
            widget.update_cursor()

        self.ui.update_status()

    def _move_cursor_to_char(
        self,
        char_x: CharCoord,
        char_y: CharCoord,
    ) -> None:
        status = self.status
        cell_format_length = status.cell_format_length

        cursor_digit = char_x % cell_format_length
        cursor_cell_x = char_x // cell_format_length
        cursor_cell_y = char_y

        self.set_cursor_cell(cursor_cell_x, cursor_cell_y, cursor_digit)

    def _move_cursor_by_char(
        self,
        char_x: CharCoord,
        char_y: CharCoord,
    ) -> None:
        status = self.status
        cursor_cell_x, cursor_cell_y = status.cursor_cell
        cursor_digit = status.cursor_digit
        cell_format_length = status.cell_format_length
        line_length = status.line_length

        cursor_digit += char_x
        cursor_cell_x += cursor_digit // cell_format_length
        cursor_digit %= cell_format_length
        cursor_cell_y += char_y + (cursor_cell_x // line_length)
        cursor_cell_x %= line_length

        self.set_cursor_cell(cursor_cell_x, cursor_cell_y, cursor_digit)

    def goto_memory_absolute(self, address: Address, selecting: bool = False) -> None:
        status = self.status
        cursor_cell_x, cursor_cell_y = status.address_to_cell_coords(address)
        self.set_cursor_cell(cursor_cell_x, cursor_cell_y, 0)
        self._update_selection(selecting)

    def goto_memory_relative(self, delta: Address, selecting: bool = False) -> None:
        status = self.status
        address = status.cursor_address + delta
        self.goto_memory_absolute(address, selecting=selecting)

    def goto_memory_start(self, selecting: bool = False) -> None:
        status = self.status
        cell_format_length = status.cell_format_length
        cell_x, cell_y = status.address_to_cell_coords(status.memory.start)
        self._move_cursor_to_char((cell_x * cell_format_length), cell_y)
        self._update_selection(selecting)

    def goto_memory_endin(self, selecting: bool = False) -> None:
        status = self.status
        cell_format_length = status.cell_format_length
        cell_x, cell_y = status.address_to_cell_coords(max(status.memory.start, status.memory.endex - 1))
        self._move_cursor_to_char((cell_x * cell_format_length) + (cell_format_length - 1), cell_y)
        self._update_selection(selecting)

    def goto_memory_endex(self, selecting: bool = False) -> None:
        status = self.status
        cell_format_length = status.cell_format_length
        cell_x, cell_y = status.address_to_cell_coords(status.memory.endex)
        self._move_cursor_to_char((cell_x * cell_format_length), cell_y)
        self._update_selection(selecting)

    def goto_line_start(self, selecting: bool = False) -> None:
        status = self.status
        cell_format_length = status.cell_format_length
        status.cursor_digit = 0
        delta = (status.cursor_cell[0] * cell_format_length)
        self._move_cursor_by_char(-delta, 0)
        self._update_selection(selecting)

    def goto_line_endin(self, selecting: bool = False) -> None:
        status = self.status
        cell_format_length = status.cell_format_length
        status.cursor_digit = cell_format_length - 1
        char_endin = (status.line_length - 1) * cell_format_length
        delta = (status.cursor_cell[0] * cell_format_length)
        delta = char_endin - delta
        self._move_cursor_by_char(+delta, 0)
        self._update_selection(selecting)

    def goto_line_endex(self, selecting: bool = False) -> None:
        status = self.status
        cell_format_length = status.cell_format_length
        status.cursor_digit = cell_format_length - 1
        delta = (status.cursor_cell[0] * cell_format_length)
        delta = (status.line_length - 1) * cell_format_length - delta
        self._move_cursor_by_char(delta, 0)
        self._update_selection(selecting)

    def goto_block_start(self, selecting: bool = False):
        status = self.status
        memory_blocks = status.memory._blocks
        cursor_address = status.cursor_address
        block_index = _hb.locate_at(memory_blocks, cursor_address)
        if block_index is None:
            # Cursor within emptiness
            block_index = _hb.locate_start(memory_blocks, cursor_address) - 1
            if block_index < 0:
                # If before memory start, no action is performed
                pass
            else:
                # If within a hole, go to the start of the hole
                block_start, block_items = memory_blocks[block_index]
                block_endex = block_start + len(block_items)
                self.goto_memory_absolute(block_endex, selecting=selecting)
        else:
            # Cursor within an actual block
            block_start, block_items = memory_blocks[block_index]
            block_endex = block_start + len(block_items)
            if block_start < block_endex:
                # Block has actual items, go to its start
                self.goto_memory_absolute(block_start, selecting=selecting)
            else:
                # Block is actually empty, no action is performed
                pass

    def goto_block_endin(self, selecting: bool = False):
        status = self.status
        memory_blocks = status.memory._blocks
        cursor_address = status.cursor_address
        block_index = _hb.locate_at(memory_blocks, cursor_address)
        if block_index is None:
            # Cursor within emptiness
            block_index = _hb.locate_start(memory_blocks, cursor_address)
            if block_index < len(memory_blocks):
                # If within a hole, go to the end of the hole
                block_start, _ = memory_blocks[block_index]
                self.goto_memory_absolute(block_start - 1, selecting=selecting)
            else:
                # If after memory end, no action is performed
                pass
        else:
            # Cursor within an actual block
            block_start, block_items = memory_blocks[block_index]
            block_endex = block_start + len(block_items)
            if block_start < block_endex:
                # Block has actual items, go to its end
                self.goto_memory_absolute(block_endex - 1, selecting=selecting)
            else:
                # Block is actually empty, no action is performed
                pass

    def goto_block_previous(self, selecting: bool = False):
        status = self.status
        memory_blocks = status.memory._blocks
        cursor_address = status.cursor_address
        block_index = _hb.locate_start(memory_blocks, cursor_address) - 1
        while block_index >= 0:
            # Block available
            block_start, block_items = memory_blocks[block_index]
            block_endex = block_start + len(block_items)
            if block_start < block_endex:
                # Block has actual items, go to its end
                self.goto_memory_absolute(block_endex - 1, selecting=selecting)
                break
            else:
                # Block is actually empty, skip it
                block_index -= 1
        else:
            # No valid previous blocks, no action is performed
            pass

    def goto_block_next(self, selecting: bool = False):
        status = self.status
        memory_blocks = status.memory._blocks
        cursor_address = status.cursor_address
        block_index = _hb.locate_endex(memory_blocks, cursor_address)
        while block_index < len(memory_blocks):
            # Block available
            block_start, block_items = memory_blocks[block_index]
            block_endex = block_start + len(block_items)
            if block_start < block_endex:
                # Block has actual items, go to its start
                self.goto_memory_absolute(block_start, selecting=selecting)
                break
            else:
                # Block is actually empty, skip it
                block_index += 1
        else:
            # No valid next blocks, no action is performed
            pass

    def move_up(self, delta_y: CellCoord = 1, selecting: bool = False) -> None:
        self._move_cursor_by_char(0, -delta_y)
        self._update_selection(selecting)

    def move_down(self, delta_y: CellCoord = 1, selecting: bool = False) -> None:
        self._move_cursor_by_char(0, +delta_y)
        self._update_selection(selecting)

    def move_page_up(self, selecting: bool = False) -> None:
        self.move_up(self.ui.editor.get_half_page_height(), selecting=selecting)

    def move_page_down(self, selecting: bool = False) -> None:
        self.move_down(self.ui.editor.get_half_page_height(), selecting=selecting)

    def move_left(self, whole_byte: bool = True, selecting: bool = False) -> None:
        status = self.status
        if status.sel_mode and not selecting:
            if status.sel_endin_address < status.sel_start_address:
                cell_x_start, cell_y_start = status.sel_endin_cell
            else:
                cell_x_start, cell_y_start = status.sel_start_cell
            self.set_cursor_cell(cell_x_start, cell_y_start, 0)
        else:
            if whole_byte:
                status.cursor_digit = 0
                self._move_cursor_by_char(-status.cell_format_length, 0)
            else:
                self._move_cursor_by_char(-1, 0)
        self._update_selection(selecting)

    def move_right(self, whole_byte: bool = True, selecting: bool = False) -> None:
        status = self.status
        if status.sel_mode and not selecting:
            if status.sel_endin_address < status.sel_start_address:
                cell_x_endin, cell_y_endin = status.sel_start_cell
            else:
                cell_x_endin, cell_y_endin = status.sel_endin_cell
            self.set_cursor_cell(cell_x_endin, cell_y_endin, 0)
            whole_byte = True  # one more

        if whole_byte:
            status.cursor_digit = status.cell_format_length - 1
            self._move_cursor_by_char(+status.cell_format_length, 0)
        else:
            self._move_cursor_by_char(+1, 0)
        self._update_selection(selecting)

    def on_file_new(self) -> None:
        self.ui.create_new()

    def _file_load(self, file_path: str) -> Memory:
        del self
        try:
            record_type = _hr.find_record_type(file_path)
        except KeyError:
            with open(file_path, 'rb') as stream:
                data = stream.read()
            memory = Memory.from_bytes(data)
        else:
            blocks = _hr.load_blocks(file_path, record_type=record_type)
            memory = Memory.from_blocks(blocks)
        return memory

    def on_file_open(self) -> None:
        file_path = self.ui.ask_open_file_path()
        if file_path:
            memory = self._file_load(file_path)

            status = self.status
            status.memory = memory
            status.file_path = file_path
            self.ui.update_title_by_file_path()

            self.goto_memory_start()
            self.ui.editor.scroll_top()
            self.ui.editor.focus_set()

    def on_file_import(self) -> None:
        file_path = self.ui.ask_open_file_path()
        if file_path:
            memory = self._file_load(file_path)
            merged = self.status.memory
            for start, items in memory._blocks:
                merged.write(start, items)

    def _file_save(self, file_path: str, memory: Memory) -> None:
        try:
            record_type = _hr.find_record_type(file_path)
        except KeyError:
            if memory.contiguous:
                with open(file_path, 'wb') as stream:
                    for start, items in memory._blocks:
                        stream.write(items)
            else:
                self.ui.show_error('Not contiguous',
                                   'Cannot save a non-contiguous\n'
                                   'chunk of data as binary file')
        else:
            _hr.save_blocks(file_path, memory._blocks, record_type=record_type)

    def on_file_save(self) -> None:
        status = self.status

        if status.file_path:
            self._file_save(status.file_path, self.status.memory)
            self.ui.update_title_by_file_path()
        else:
            self.on_file_save_as()

    def on_file_save_as(self) -> None:
        file_path = self.ui.ask_save_file_path()
        if file_path:
            self._file_save(file_path, self.status.memory)

            status = self.status
            status.file_path = file_path
            self.ui.update_title_by_file_path()

    def on_file_settings(self) -> None:
        _todo()  # TODO

    def on_file_exit(self) -> None:
        # TODO: check for changes and ask for confirmation
        self.ui.quit()

    def on_edit_undo(self) -> None:
        self.on_key_undo()

    def on_edit_redo(self) -> None:
        self.on_key_redo()

    def on_edit_cut(self) -> None:
        self.copy_selection()
        self.delete_selection()

    def on_edit_copy(self) -> None:
        self.copy_selection()

    def on_edit_paste(self) -> None:
        self.paste_selection()

    def on_edit_delete(self) -> None:
        self.delete_cell()

    def on_edit_cursor_mode(self) -> None:
        self.switch_cursor_mode()

    def on_edit_clear(self) -> None:
        self.clear_cell()

    def on_edit_reserve(self) -> None:
        self.reserve_cell()

    def on_edit_fill(self) -> None:
        self.on_key_fill()

    def on_edit_flood(self) -> None:
        self.on_key_flood()

    def on_edit_crop(self) -> None:
        self.crop_selection()

    def on_edit_move_focus(self) -> None:
        self.on_nav_goto_memory_address_start_focus()

    def on_edit_move_apply(self) -> None:
        _todo()  # TODO

    def on_edit_export(self) -> None:
        status = self.status
        path = self.ui.ask_save_file_path()
        if path and status.sel_mode:
            start = status.sel_start_address
            endin = status.sel_endin_address
            if endin < start:
                endin, start = start, endin
            memory = status.memory.extract(start, endin + 1)
            _hr.save_blocks(path, memory._blocks)

    def on_edit_select_all(self) -> None:
        self.select_all()

    def on_edit_select_range(self) -> None:
        self.on_nav_goto_memory_address_endin_apply()

    def on_edit_copy_address(self) -> None:
        self.copy_cursor_address()

    def on_edit_find(self) -> None:
        _todo()  # TODO

    def on_view_line_length_custom(self) -> None:
        self.ui.ask_line_length_custom()

    def on_view_address_bits_custom(self) -> None:
        self.ui.ask_address_bits_custom()

    def on_view_chars_encoding_custom(self) -> None:
        self.ui.ask_chars_encoding_custom()

    def on_view_redraw(self) -> None:
        self.ui.editor.redraw()
        self.ui.update_status()

    def on_nav_editor_focus(self) -> None:
        self.ui.editor.focus_set()

    def on_nav_goto_memory_address_start_focus(self) -> None:
        self.ui.focus_start_text()

    def on_nav_goto_memory_address_start_apply(self) -> None:
        ui = self.ui
        try:
            address = ui.get_start_address()
        except ValueError:
            ui.set_start_text('', focus=True)
        else:
            self.goto_memory_absolute(address)
            ui.editor.focus_set()

    def on_nav_goto_memory_address_endin_focus(self) -> None:
        self.ui.focus_endin_text()

    def on_nav_goto_memory_address_endin_apply(self) -> None:
        ui = self.ui
        try:
            start_address = ui.get_start_address()
        except ValueError:
            ui.set_start_text('', focus=True)
            return

        try:
            endin_address = ui.get_endin_address()
        except ValueError:
            ui.set_endin_text('', focus=True)
            return

        if endin_address < start_address:
            endin_address = start_address - 1  # no selection
        self.select_range(start_address, endin_address + 1)
        ui.editor.focus_set()

    def on_nav_goto_memory_address_copy(self) -> None:
        status = self.status
        ui = self.ui

        if status.sel_mode:
            start_address = status.sel_start_address
            endin_address = status.sel_endin_address
            if endin_address < start_address:
                endin_address, start_address = start_address, endin_address
            ui.set_start_address(start_address)
            ui.set_endin_address(endin_address)
        else:
            ui.set_start_address(status.cursor_address)
            ui.set_endin_text('')

        ui.editor.focus_set()

    def on_nav_goto_memory_start(self) -> None:
        self.goto_memory_start()

    def on_nav_goto_memory_endin(self) -> None:
        self.goto_memory_endin()

    def on_nav_goto_memory_endex(self) -> None:
        self.goto_memory_endex()

    def on_nav_address_skip(self) -> None:
        self.ui.ask_address_skip_custom()

    def on_nav_goto_block_previous(self) -> None:
        self.on_key_goto_block_previous()

    def on_nav_goto_block_next(self) -> None:
        self.on_key_goto_block_next()

    def on_nav_goto_block_start(self) -> None:
        self.on_key_goto_block_start()

    def on_nav_goto_block_endin(self) -> None:
        self.on_key_goto_block_endin()

    def on_nav_goto_byte_previous(self) -> None:
        self.on_key_move_left_byte()

    def on_nav_goto_byte_next(self) -> None:
        self.on_key_move_right_byte()

    def on_nav_goto_line_start(self) -> None:
        self.goto_line_start()

    def on_nav_goto_line_endin(self) -> None:
        self.goto_line_endin()

    def on_nav_scroll_line_up(self) -> None:
        self.ui.editor.scroll_up()

    def on_nav_scroll_line_down(self) -> None:
        self.ui.editor.scroll_down()

    def on_nav_scroll_page_up(self) -> None:
        self.ui.editor.scroll_page_up()

    def on_nav_scroll_page_down(self) -> None:
        self.ui.editor.scroll_page_down()

    def on_nav_scroll_top(self) -> None:
        self.ui.editor.scroll_top()

    def on_nav_scroll_bottom(self) -> None:
        self.ui.editor.scroll_bottom()

    def on_help_about(self) -> None:
        self.ui.show_about()

    def on_set_chars_visible(self, visible: bool) -> None:
        self.ui.editor.chars_visible = visible

    def on_set_line_length(self, line_length: CellCoord) -> None:
        status = self.status
        status.line_length = line_length
        self.goto_memory_absolute(status.cursor_address)

    def on_set_chars_encoding(self, encoding: str) -> None:
        status = self.status
        status.chars_encoding = encoding
        status.chars_table = build_encoding_table(encoding)
        self.on_view_redraw()

    def on_set_cell_mode(self, mode: ValueFormatEnum) -> None:
        status = self.status
        status.cell_format_mode = ValueFormatEnum(mode)
        status.update_cell_format()
        self.on_view_redraw()

    def on_set_cell_prefix(self, prefix: bool) -> None:
        status = self.status
        status.cell_format_prefix = bool(prefix)
        status.update_cell_format()
        self.on_view_redraw()

    def on_set_cell_suffix(self, suffix: bool) -> None:
        status = self.status
        status.cell_format_suffix = bool(suffix)
        status.update_cell_format()
        self.on_view_redraw()

    def on_set_cell_zeroed(self, zeroed: bool) -> None:
        status = self.status
        status.cell_format_zeroed = bool(zeroed)
        status.update_cell_format()
        self.on_view_redraw()

    def on_set_address_mode(self, mode: ValueFormatEnum) -> None:
        status = self.status
        status.address_format_mode = ValueFormatEnum(mode)
        status.update_address_format()
        self.on_view_redraw()

    def on_set_address_prefix(self, prefix: bool) -> None:
        status = self.status
        status.address_format_prefix = bool(prefix)
        status.update_address_format()
        self.on_view_redraw()

    def on_set_address_suffix(self, suffix: bool) -> None:
        status = self.status
        status.address_format_suffix = bool(suffix)
        status.update_address_format()
        self.on_view_redraw()

    def on_set_address_zeroed(self, zeroed: bool) -> None:
        status = self.status
        status.address_format_zeroed = bool(zeroed)
        status.update_address_format()
        self.on_view_redraw()

    def on_set_address_skip(self, skip: Address) -> None:
        status = self.status
        status.address_skip = skip
        self.on_view_redraw()

    def on_set_address_bits(self, bitsize: int) -> None:
        status = self.status
        status.address_bits = bitsize
        status.update_address_format()
        self.on_view_redraw()

    def on_set_offset_mode(self, mode: ValueFormatEnum) -> None:
        status = self.status
        status.offset_format_mode = ValueFormatEnum(mode)
        status.update_offset_format()
        self.on_view_redraw()

    def on_set_offset_prefix(self, prefix: bool) -> None:
        status = self.status
        status.offset_format_prefix = bool(prefix)
        status.update_offset_format()
        self.on_view_redraw()

    def on_set_offset_suffix(self, suffix: bool) -> None:
        status = self.status
        status.offset_format_suffix = bool(suffix)
        status.update_offset_format()
        self.on_view_redraw()

    def on_set_offset_zeroed(self, zeroed: bool) -> None:
        status = self.status
        status.offset_format_zeroed = bool(zeroed)
        status.update_offset_format()
        self.on_view_redraw()

    def on_key_digit_cells(self, digit_char: str):
        insert = (self.status.cursor_mode == CursorMode.INSERT)
        self.write_digit(digit_char, insert=insert)

    def on_key_digit_chars(self, digit_char: str):
        try:
            value = self.status.chars_table.index(digit_char)
        except ValueError:
            pass
        else:
            insert = (self.status.cursor_mode == CursorMode.INSERT)
            self.write_byte(value, insert=insert)

    def on_key_reserve_cell(self):
        self.reserve_cell()

    def on_key_delete_cell(self):
        self.delete_cell()

    def on_key_clear_cell(self):
        self.clear_cell()

    def on_key_clear_back(self):
        if self.status.cursor_mode == CursorMode.INSERT:
            self.move_left(whole_byte=True)
            self.delete_cell()
        else:
            sel_mode = self.status.sel_mode
            self.clear_cell()
            if not sel_mode:
                self.move_left(whole_byte=True)

    def on_key_clear_next(self):
        sel_mode = self.status.sel_mode
        self.clear_cell()
        if not sel_mode:
            self.move_right(whole_byte=True)

    def on_key_delete(self):
        if self.status.cursor_mode == CursorMode.INSERT:
            self.delete_cell()
        else:
            self.on_key_clear_next()

    def on_key_fill(self):
        # FIXME: ask to view/widget
        answer = tkinter.simpledialog.askstring('Fill value', 'Insert the fill value')
        if answer:
            try:
                value = parse_int(answer)[0]
                self.fill_selection(value)
            except ValueError:
                tkinter.messagebox.showerror('Invalid format', f'Invalid value format:\n\n{answer}')
        self.ui.editor.focus_set()

    def on_key_flood(self):
        status = self.status
        if status.memory.peek(status.cursor_address) is None or status.sel_mode:
            # FIXME: ask to view/widget
            answer = tkinter.simpledialog.askstring('Flood value', 'Insert the flood value')
            if answer:
                try:
                    value = parse_int(answer)[0]
                    self.flood_selection(value)
                except ValueError:
                    tkinter.messagebox.showerror('Invalid format', f'Invalid value format:\n\n{answer}')
            self.ui.editor.focus_set()

    def on_key_cut(self):
        self.cut_selection()

    def on_key_copy(self):
        self.copy_selection()

    def on_key_paste(self):
        self.paste_selection()

    def on_key_crop(self):
        self.crop_selection()

    def on_key_move_focus(self):
        self.on_nav_goto_memory_address_start_focus()

    def on_key_move_apply(self):
        # TODO: read from toolbar
        self.ui.editor.focus_set()

    def on_key_scroll_line_up(self):
        self.ui.editor.scroll_up()

    def on_key_scroll_page_up(self):
        self.ui.editor.scroll_page_up()

    def on_key_scroll_line_down(self):
        self.ui.editor.scroll_down()

    def on_key_scroll_page_down(self):
        self.ui.editor.scroll_page_down()

    def on_key_scroll_top(self):
        self.ui.editor.scroll_top()

    def on_key_scroll_bottom(self):
        self.ui.editor.scroll_bottom()

    def on_key_move_left_digit(self, selecting: bool = False):
        self.move_left(whole_byte=selecting, selecting=selecting)

    def on_key_move_right_digit(self, selecting: bool = False):
        self.move_right(whole_byte=selecting, selecting=selecting)

    def on_key_move_left_byte(self, selecting: bool = False):
        self.move_left(whole_byte=True, selecting=selecting)

    def on_key_move_right_byte(self, selecting: bool = False):
        self.move_right(whole_byte=True, selecting=selecting)

    def on_key_move_line_up(self, selecting: bool = False):
        self.move_up(selecting=selecting)

    def on_key_move_page_up(self, selecting: bool = False):
        self.move_page_up(selecting=selecting)

    def on_key_move_line_down(self, selecting: bool = False):
        self.move_down(selecting=selecting)

    def on_key_move_page_down(self, selecting: bool = False):
        self.move_page_down(selecting=selecting)

    def on_key_goto_line_start(self, selecting: bool = False):
        self.goto_line_start(selecting=selecting)

    def on_key_goto_line_endin(self, selecting: bool = False):
        self.goto_line_endin(selecting=selecting)

    def on_key_goto_memory_apply(self):
        self.escape_selection()
        # TODO: read from toolbar
        self.ui.editor.focus_set()

    def on_key_goto_memory_focus(self):
        self.on_nav_goto_memory_address_start_focus()

    def on_key_goto_memory_start(self, selecting: bool = False):
        self.goto_memory_start(selecting=selecting)

    def on_key_goto_memory_endin(self, selecting: bool = False):
        self.goto_memory_endin(selecting=selecting)

    def on_key_goto_memory_endex(self, selecting: bool = False):
        self.goto_memory_endex(selecting=selecting)

    def on_key_goto_block_previous(self, selecting: bool = False):
        self.goto_block_previous(selecting=selecting)

    def on_key_goto_block_next(self, selecting: bool = False):
        self.goto_block_next(selecting=selecting)

    def on_key_goto_block_start(self, selecting: bool = False):
        self.goto_block_start(selecting=selecting)

    def on_key_goto_block_endin(self, selecting: bool = False):
        self.goto_block_endin(selecting=selecting)

    def on_key_copy_address(self):
        self.copy_cursor_address()

    def on_key_set_address(self):
        self.on_nav_goto_memory_address_copy()

    def on_key_select_all(self):
        self.select_all()

    def on_key_select_range(self):
        _todo()  # TODO: focus toolbar

    def on_key_escape_selection(self):
        self.escape_selection()

    def on_key_switch_cursor_mode(self):
        self.switch_cursor_mode()

    def on_key_redraw(self):
        self.ui.editor.redraw()

    def on_key_undo(self):
        _todo()  # TODO

    def on_key_redo(self):
        _todo()  # TODO

    def on_cells_selection_press(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        self.set_cursor_cell(cell_x, cell_y, cell_digit)
        self.escape_selection()

        widget = self.ui.editor
        widget.cells_canvas.focus_set()

    def on_cells_selection_double(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        self.on_cells_selection_press(cell_x, cell_y, cell_digit)
        status = self.status
        self.select_homogeneous(status.cursor_address)

    def on_cells_selection_motion(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        status = self.status
        widget = self.ui.editor

        widget.cells_canvas.focus_set()
        cursor_cell_prev = status.cursor_cell
        self.set_cursor_cell(cell_x, cell_y, cell_digit)

        if cursor_cell_prev != status.cursor_cell or not status.sel_mode:
            if status.sel_mode == SelectionMode.OFF:
                status.sel_mode = SelectionMode.NORMAL
                self.ui.update_menus_by_selection()

            cursor_cell_x, cursor_cell_y = status.cursor_cell
            cursor_cell_x = max(0, min(floor(cursor_cell_x), status.line_length - 1))
            cursor_cell_y = floor(cursor_cell_y)
            self._set_selection_endin(cursor_cell_x, cursor_cell_y)

            cell_start_y = widget.view_start_cell[1]
            cell_endex_y = widget.view_end_cell[1] + 1

            if cursor_cell_y < cell_start_y or cursor_cell_y >= cell_endex_y:
                self.set_cursor_cell(cursor_cell_x, cursor_cell_y, status.cursor_digit)

            widget.update_view(force_selection=True)

    def on_cells_selection_release(
        self,
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        widget = self.ui.editor
        widget.focus_set()
        widget.update_view(force_selection=True)

    def on_chars_selection_press(
        self,
        char_x: CellCoord,
        char_y: CellCoord,
    ):
        self.set_cursor_cell(char_x, char_y, 0)
        self.escape_selection()
        self.ui.editor.chars_canvas.focus_set()

    def on_chars_selection_double(
        self,
        char_x: CellCoord,
        char_y: CellCoord,
    ):
        self.on_chars_selection_press(char_x, char_y)
        self.select_homogeneous(self.status.cursor_address)

    def on_chars_selection_motion(
        self,
        char_x: CellCoord,
        char_y: CellCoord,
    ):
        status = self.status
        widget = self.ui.editor

        widget.chars_canvas.focus_set()
        cursor_cell_prev = status.cursor_cell
        self.set_cursor_cell(char_x, char_y, 0)

        if cursor_cell_prev != status.cursor_cell or not status.sel_mode:
            if status.sel_mode == SelectionMode.OFF:
                status.sel_mode = SelectionMode.NORMAL
                self.ui.update_menus_by_selection()

            cursor_cell_x, cursor_cell_y = status.cursor_cell
            cursor_cell_x = max(0, min(floor(cursor_cell_x), status.line_length - 1))
            cursor_cell_y = floor(cursor_cell_y)
            self._set_selection_endin(cursor_cell_x, cursor_cell_y)

            cell_start_y = widget.view_start_cell[1]
            cell_endex_y = widget.view_end_cell[1] + 1

            if cursor_cell_y < cell_start_y or cursor_cell_y >= cell_endex_y:
                self.set_cursor_cell(cursor_cell_x, cursor_cell_y, status.cursor_digit)

            widget.update_view(force_selection=True)

    def on_chars_selection_release(
        self,
        char_x: CellCoord,
        char_y: CellCoord,
    ):
        widget = self.ui.editor
        widget.chars_canvas.focus_set()
        widget.update_view(force_selection=True)
