*******************
PyInstaller scripts
*******************

This folder contains wrapper scripts to generate self-contained executables
with PyInstaller.


Installation
============

Make sure that ``pyinstaller`` is called by a Python environment where
``hecks`` was successfully installed.


Anaconda 3 / Windows
--------------------

For example, with Anaconda Prompt:

.. code-block:: sh

    $ conda create -n hecks_pyinstaller python=3
    $ conda activate hecks_pyinstaller
    $ pip install pyinstaller
    $ cd PATH_TO_hecks_SOURCE_ROOT
    $ python setup.py install

Note that ``pyinstaller`` might generate broken executables depending on the
installed packages. You can try with the developmental version for an updated
codebase instead of the default package:

.. code-block:: sh

    $ pip install https://github.com/pyinstaller/pyinstaller/tarball/develop


Generation
==========

Example command line to create a standalone executable:

.. code-block:: sh

    $ cd PATH_TO_hecks_SOURCE_ROOT
    $ cd pyinstaller
    $ pyinstaller hecks.spec

This will generate ``hecks`` (``hecks.exe`` under Windows) in the ``dist``
sub-folder.
