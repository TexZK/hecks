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
from typing import List
from typing import Tuple

from .common import BaseEngine
from .common import BaseMemento
from .common import CellCoord
from .common import EngineStatus
from .utils import VALUE_FORMAT_CHAR
from .utils import VALUE_FORMAT_PREFIX
from .utils import VALUE_FORMAT_SUFFIX
from .utils import ValueFormatEnum
from bytesparse.base import Address
from bytesparse.base import AnyBytes
from bytesparse.base import Value
from bytesparse.inplace import Memory


# =====================================================================================================================

class MoveCursor(BaseMemento):

    def __init__(
        self,
        engine: BaseEngine,
        status: EngineStatus,
        cell_x: CellCoord,
        cell_y: CellCoord,
        cell_digit: CellCoord,
    ):
        super().__init__(engine, status)

        self._cursor_cell_prev = status.cursor_cell
        self._cursor_digit_prev = status.cursor_digit

        self._cursor_cell_next = (cell_x, cell_y)
        self._cursor_digit_next = cell_digit

    def redo(self) -> None:
        engine = self._engine
        engine.set_cursor_cell(*self._cursor_cell_next, self._cursor_digit_next)

    def undo(self) -> None:
        engine = self._engine
        engine.escape_selection()
        engine.set_cursor_cell(*self._cursor_cell_prev, self._cursor_digit_prev)


# ---------------------------------------------------------------------------------------------------------------------

class MoveMemory(BaseMemento):

    def __init__(
        self,
        engine: BaseEngine,
        status: EngineStatus,
        offset: Address,
    ):
        super().__init__(engine, status)
        memory = status.memory
        offset, backup = memory.shift_backup(offset)

        self._offset = offset
        self._backup = backup

    def redo(self) -> None:
        engine = self._engine
        status = self._status
        memory = status.memory
        offset = self._offset

        engine.escape_selection()
        cursor_address = status.cursor_address
        memory.shift(offset)
        engine.goto_memory_absolute(cursor_address + offset)
        engine.on_view_redraw()

    def undo(self) -> None:
        engine = self._engine
        status = self._status
        memory = status.memory
        offset = self._offset
        backup = self._backup

        engine.escape_selection()
        cursor_address = status.cursor_address
        memory.shift_restore(offset, backup)
        engine.goto_memory_absolute(cursor_address - offset)
        engine.on_view_redraw()


# ---------------------------------------------------------------------------------------------------------------------

class WriteData(BaseMemento):

    def __init__(
        self,
        engine: BaseEngine,
        status: EngineStatus,
        address: Address,
        data: AnyBytes,
    ):
        super().__init__(engine, status)
        memory = status.memory
        backups = memory.write_backup(address, data)

        self._address = address
        self._data = data
        self._backups = backups

    def redo(self) -> None:
        engine = self._engine
        status = self._status
        memory = status.memory
        address = self._address
        data = self._data

        engine.escape_selection()
        memory.write(address, data)
        engine.goto_memory_absolute(address + len(data))
        engine.on_view_redraw()

    def undo(self) -> None:
        engine = self._engine
        status = self._status
        memory = status.memory
        address = self._address
        backups = self._backups

        engine.escape_selection()
        memory.write_restore(backups)
        engine.goto_memory_absolute(address)
        engine.on_view_redraw()


# ---------------------------------------------------------------------------------------------------------------------

class ClearData(BaseMemento):

    def __init__(
        self,
        engine: BaseEngine,
        status: EngineStatus,
        address: Address,
        size: int,
    ):
        super().__init__(engine, status)
        memory = status.memory
        backup = memory.clear_backup(address, address + size)

        self._address = address
        self._size = size
        self._backup = backup

    def redo(self) -> None:
        engine = self._engine
        status = self._status
        memory = status.memory
        address = self._address
        size = self._size

        engine.escape_selection()
        memory.clear(address, address + size)
        engine.goto_memory_absolute(address)
        engine.on_view_redraw()

    def undo(self) -> None:
        engine = self._engine
        status = self._status
        memory = status.memory
        address = self._address
        backup = self._backup

        engine.escape_selection()
        memory.clear_restore(backup)
        engine.goto_memory_absolute(address)
        engine.on_view_redraw()


# ---------------------------------------------------------------------------------------------------------------------

class DeleteData(BaseMemento):

    def __init__(
        self,
        engine: BaseEngine,
        status: EngineStatus,
        address: Address,
        size: int,
    ):
        super().__init__(engine, status)
        memory = status.memory
        backup = memory.delete_backup(address, address + size)

        self._address = address
        self._size = size
        self._backup = backup

    def redo(self) -> None:
        engine = self._engine
        status = self._status
        memory = status.memory
        address = self._address
        size = self._size

        engine.escape_selection()
        memory.delete(address, address + size)
        engine.goto_memory_absolute(address)
        engine.on_view_redraw()

    def undo(self) -> None:
        engine = self._engine
        status = self._status
        memory = status.memory
        address = self._address
        size = self._size
        backup = self._backup

        engine.escape_selection()
        memory.delete_restore(backup)
        engine.goto_memory_absolute(address + size)
        engine.on_view_redraw()
