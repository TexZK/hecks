# To-Do brainstorming

- refactoring
    - library-style folders (hexrec as template)
        - comment out testing features
    - init/main
    - editor
    - memory
    - controller
    - split actual gui and controller into modules

- single controller
    - provide callback class to project-specific widgets
    - route all callbacks to single controller
    - controller performs actions onto specific widgets

- fix prefix format (e.g. "0x  -1234" to "-0x1234")
- fix vertical scrollbar
- DONE! perform toolbar actions
- adaptive line width
- export multiple formats sub-menu

- byte groups
    - DONE! colored odd/even
    - at least in HEX mode

- context-sensitive menu enable/disable

- data inspector frame
    - custom entry
        - minimum chunk length
        - binary
        - integer
            - byte size
            - signed
        - character
            - ascii
            - utf-8
    - grid of label + custom entry
    - with scrollbar
    - entry overwrites
    - integer options
        - hex / dec
        - big / little endian

- selection
    - crop
    - move
    - flood
        - available also at cursor
    - select cursor neighbors with same value (or a hole)

- find / replace

- character pane
    - mouse selection
    - keyboard editing
    - encoding selection

- right-click popup menus
    - address pane
    - offset pane
    - byte view
    - characters

- settings window
    - editor font
        - filter monospace
    - colors
        - window background + text
        - highlight background + text
        - odd-column text
        - tooltip background + text

- undo / redo
    - deque

- editable virtual memory
    - like hexrec.blocks.Memory
    - using bytearray for block items
    - in-place editing wherever possible

- theme management
    - default
    - dark mode

- mini-map
