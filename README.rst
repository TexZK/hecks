********
Overview
********

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - | |requires|
    * - package
      - | |version| |wheel| |supported-versions| |supported-implementations|
        | |commits-since|

.. |docs| image:: https://readthedocs.org/projects/hecks/badge/?style=flat
    :target: https://readthedocs.org/projects/hecks
    :alt: Documentation Status

.. |requires| image:: https://requires.io/github/TexZK/hecks/requirements.svg?branch=main
    :alt: Requirements Status
    :target: https://requires.io/github/TexZK/hecks/requirements/?branch=main

.. |version| image:: https://img.shields.io/pypi/v/hecks.svg
    :alt: PyPI Package latest release
    :target: https://pypi.org/project/hecks/

.. |commits-since| image:: https://img.shields.io/github/commits-since/TexZK/hecks/v0.0.1.svg
    :alt: Commits since latest release
    :target: https://github.com/TexZK/hecks/compare/v0.0.1...main

.. |wheel| image:: https://img.shields.io/pypi/wheel/hecks.svg
    :alt: PyPI Wheel
    :target: https://pypi.org/project/hecks/

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/hecks.svg
    :alt: Supported versions
    :target: https://pypi.org/project/hecks/

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/hecks.svg
    :alt: Supported implementations
    :target: https://pypi.org/project/hecks/


.. end-badges

Hexadecimal editor

* Free software: GNU General Public License version 3 License
* Icons based on the `BlueSphere` project: http://svgicons.sourceforge.net/


WORK IN PROGRESS
================

The project is in a **pre-alpha** state. Most of the basic features should be
working, but there are even more features disabled or yet to be added.

Throughout the source code, known bugs and missing features are marked as
``FIXME`` or ``TODO``.

Overall to-do list
------------------

* Refactor direct GUI calls from engine
* Add GUI arguments from the command line (CLI-like)
* Add undo/redo feature
* Add find/replace feature
* Add options window
* Add export options window
* Add direct file support
* Add column grouping
* Add address space restrictions (e.g. not negative)
* Add documentation
* ... and many more bells and whistles (aka `bug fixing`)!


Direct GUI launch
=================

After installing the ``hecks`` package, the GUI can be launched directly
with the ``hecks_gui.py`` script (actually made for ``pyinstaller``):

.. code-block:: sh

    $ python pyinstaller/hecks_gui.py

This workflow will likely change in the future.


Documentation
=============

For the full documentation, please refer to:
**(NOT YET AVAILABLE)**

https://hecks.readthedocs.io/


Installation
============

From PIP (might not be the latest version found on *github*):
**(NOT YET AVAILABLE)**

.. code-block:: sh

    $ pip install hecks

From source:

.. code-block:: sh

    $ python setup.py install
