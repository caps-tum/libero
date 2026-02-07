# LIBERO

LIBERO is a flexible, lightweight gdb-plugin for visualization of the RISC-V Vector Extension (RVV).

## Installation

Included is an installation script which copies a `.gdbinit` file to the home directory, which is loaded by gdb on start. This init-file auto-loads the plugin and also creates a sample TUI layout, so LIBERO can be used right out of the box. Therefore, installation is as simple as running

```
> ./install.sh
```

And uninstalation, conversely, works by executing

```
> ./uninstall.sh
```

Of course, you can opt to source the plugin manually in gdb by running

```
(gdb) source src/libero.py
```

## Usage

When you have the plugin loaded in gdb, you can use it as follows:
1. Create a new layout containing the new vector window: 
```
tui new-layout [name] cmd 1 vectors 1 [...]
```
2. Set a breakpoint and start program execution
3. Upon hitting a breakpoint (or whenever you want to access the layout), run 
```
layout [name]
```

LIBERO now provides you a couple of custom commands, which can be used to configure its behavior:
```
pin [all/NAME] - add all vector registers/a specific vector or status register by name to the list of watched vectors
unpin [all/NAME] - remove all vector registers/a specific vector or status register by name
togglehex - toggle between decimal and hexadecimal display of contents
```
