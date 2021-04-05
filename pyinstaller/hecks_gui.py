"""
Run PyInstaller against this script file to build a standalone executable.
Make sure that hecks is installed into the Python environment before.
"""

from hecks.engine import Engine
from hecks.tkgui import UserInterface
from hecks.tkgui import InstanceManager

manager = InstanceManager()
UserInterface(manager, Engine)
manager.run()
