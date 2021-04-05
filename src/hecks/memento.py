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

from .common import BaseEngine
from .common import BaseMemento
from .common import CellCoord
from .common import EngineStatus
from .utils import VALUE_FORMAT_CHAR
from .utils import VALUE_FORMAT_PREFIX
from .utils import VALUE_FORMAT_SUFFIX
from .utils import ValueFormatEnum
from bytesparse._py import Address
from bytesparse._py import Memory
from bytesparse._py import Value


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
        self._offset: Address = offset

    def redo(self) -> None:
        self._engine.shift_memory(self._offset)  # FIXME: restore trimmed chunks

    def undo(self) -> None:
        self._engine.shift_memory(-self._offset)  # FIXME: restore trimmed chunks


# ---------------------------------------------------------------------------------------------------------------------
class WriteData(BaseMemento):

    def __init__(
        self,
        engine: BaseEngine,
        status: EngineStatus,
    ):
        super().__init__(engine, status)

    def redo(self) -> None:
        raise NotImplementedError  # TODO

    def undo(self) -> None:
        raise NotImplementedError  # TODO
