import gdb
import re

def get_vector_register_value(reg_name):
    """Get the value of a specific vector register."""

    try:
        val = gdb.parse_and_eval("$" + reg_name)
        word_field = val.type["b"]
        values = val[word_field]
        arr_range = values.type.range()

        reg_val = []
        for i in range(arr_range[0], arr_range[1] + 1):
            reg_val.append(values[i].bytes)
        return reg_val
    except gdb.error as e:
        return None
    
def get_status_register_value(reg_name):
    """Get the value of a specific status register."""

    try:
        val = gdb.parse_and_eval("$" + reg_name)
        return val.bytes
    except gdb.error as e:
        return None

def get_instruction():
    f = gdb.selected_frame()
    pc = f.pc()
    ins = f.architecture().disassemble(pc, count=1)
    return ins[0]

def is_masked_op():
    instr = get_instruction()['asm']
    if "v0.t" in instr:
        return True
    else:
        False

def get_mask():
    instr = get_instruction()['asm']
    if "v0.t" in instr:
        vl = int.from_bytes(get_status_register_value("vl"), "little")
        mask_reg = get_status_register_value("v0")
        mask_int = int.from_bytes(mask_reg, "little", signed=False)
        bits = [(mask_int >> i) & 1 for i in range(vl)]
        return bits
    else:
        return None

def get_vstart():
    return int.from_bytes(get_status_register_value("vstart"), "little")
def get_vl():
    return int.from_bytes(get_status_register_value("vl"), "little")


def get_sew_lmul():
    vtype = int.from_bytes(get_status_register_value("vtype"), "little")
    vsew = (vtype >> 3) & 0b111
    if vsew == 0:
        vsew = 8
    elif vsew == 1:
        vsew = 16
    elif vsew == 2:
        vsew = 32
    elif vsew == 3:
        vsew = 64
    else:
        vsew = 8 # so far, the spec doesnt specify any value greater than 64; default to 8

    vlmul = vtype & 0b111
    if vlmul <=3:
        vlmul = 1 << vlmul
    elif vlmul == 5:
        vlmul = 1/8
    elif vlmul == 6:
        vlmul = 1/4
    elif vlmul == 7:
        vlmul = 1/2
    else:
        vlmul = 1

    return vsew, vlmul

def get_active_elements():
    sew, lmul = get_sew_lmul()
    vlenb = int.from_bytes(get_status_register_value("vlenb"), "little")
    vstart = get_vstart()
    vl = get_vl()

    vlmax = int((vlenb * 8 * lmul) // sew)

    head = min(vstart, vl)
    active = max(vl - vstart, 0)
    tail = max(vlmax - vl, 0)

    active = [1 if (vstart <= i < vl) else 0 for i in range(vlmax)]

    mask = get_mask()
    if mask is not None:
        upto = min(vl, len(mask))
        for i in range(upto):
            if active[i] == 1 and mask[i] != 1:
                active[i] = 0
    return active 


#TODO for now segmented load/store instructions are ignored
"""
    all depend on LMUL if LMUL > 1, but LMUL is already handled by the visualization
    executing segmented instructions with EEW != SEW is illegal
Loads: 
    - vlseg{1..8}e{8|16|32|64}.v
    - vlseg{1..8}e{8|16|32|64}ff.v
    - vlsseg{1..8}e{8|16|32|64}.v
        loads into registers vsrc...vsrc+nf
        e{8|16|32|64} for element width
        mask same for each vector
    - vluxseg{1..8}ei{8|16|32|64}.v
        - indexed-unordered segment loads
        - nf: number of elements stored (each in extra reg)
        - {8|16|32|64} with of index elements in source vector
    - vloxseg{1..8}ei{8|16|32|64}.v
        - indexed-ordered segment loads.
        - like vlux but loads are done in increasing index order
Stores: 
    - vsseg{1..8}e{8|16|32|64}.v
    - vssseg{1..8}e{8|16|32|64}.v
    loads from registers vsrc...vsrc+nf
    e{8|16|32|64}
    - vsuxseg{1..8}ei{8|16|32|64}.v
    - vsoxseg{1..8}ei{8|16|32|64}.v
"""

# regex to find segment factor
SEG_TWO_NUM_PAT = re.compile(
    r"^(?:"
    r"vl(?:ux|ox)?seg"      # vlseg, vluxseg, vloxseg
    r"|vlsseg"              # strided load
    r"|vs(?:ux|ox)?seg"     # vsseg, vsuxseg, vsoxseg
    r"|vssseg"              # strided store
    r")"
    r"(\d+)"                # first number
    r"(?:e|ei)"             # e/ei
    r"(8|16|32|64)"         # second number
    r"(?:ff)?\.v$",         # optional ff for vlseg…ff.v)
    re.IGNORECASE           # should not be needed, but just in case ;)
)

def segment_factor(mn):
    m = SEG_TWO_NUM_PAT.match(mn.strip())
    if not m:
        return None
    nf, eew = m.groups()
    return int(nf), int(eew)



def get_masked_result_or_store_src():
    """
    Returns starting vector element of src/dst and how many vector groups are involved in instruction
    For arithm, converts, shifts we want to hilight dst register with mask
    For Loads/Stores the register that is loaded from/stored to
    For segmented ops same as for loads/stores
    """
     
    instr = get_instruction()
    parts = instr['asm'].split(None, 1)
    mn = parts[0].lower()

    ops_str = parts[1]
    ops = [o.strip() for o in ops_str.split(",")]
    dest = ops[0]

    if segment_factor(mn) is not None:
        nf, eew = segment_factor(nm)
        return dest, nf

    # even for higher lmuls only the first register is passed
    return dest, 1

ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

def ansi_stripped_len(s: str) -> int:
    return len(ANSI_RE.sub('', s))    

def ansi_center(s: str, width: int) -> str:
    vis = ansi_stripped_len(s)
    if vis >= width:
        return s
    pad = width - vis
    return ' ' * (pad // 2) + s + ' ' * (pad - pad // 2)

    

    
class VectorWindow:

    pinned_stat_regs = ["vlenb", "vl", "vtype"]
    pinned_vec_regs = ["v1", "v2", "v3", "v4", "v5", "v6", "v7", "v23", "v24", "v25"]

    stat_regs_content = {}
    vec_regs_content = {}

    hex_display = True

    def __init__(self, tui_window):
        self._tui_window = tui_window
        self._tui_window_title = "Vector Registers"
        self._step_listener = self.step_listener
        self.scroll_offset = 0
        self.lines = []
        gdb.events.stop.connect(self._step_listener)


    def step_listener(self, event):
        self.render()

    def poll_stat_regs(self):
        stat_regs_content_old = self.stat_regs_content.copy()
        for reg in stat_regs_content_old.keys():
            if reg not in self.pinned_stat_regs:
                del self.stat_regs_content[reg]
        for reg in self.pinned_stat_regs:
            self.stat_regs_content[reg] = get_status_register_value(reg)

    def poll_vec_regs(self):
        vec_regs_content_old = self.vec_regs_content.copy()
        for reg in vec_regs_content_old.keys():
        #    if reg not in self.pinned_vec_regs:
            del self.vec_regs_content[reg]

        vlenb = int.from_bytes(get_status_register_value("vlenb"), "little")
        vtype = int.from_bytes(get_status_register_value("vtype"), "little")
        vsew = (vtype >> 3) & 0b111
        if vsew == 0:
            vsew = 8
        elif vsew == 1:
            vsew = 16
        elif vsew == 2:
            vsew = 32
        elif vsew == 3:
            vsew = 64
        else:
            vsew = 8 # so far, the spec doesnt specify any value greater than 64; default to 8

        vlmul = vtype & 0b111
        if vlmul <=3:
            vlmul = 1 << vlmul
        elif vlmul == 5:
            vlmul = 1/8
        elif vlmul == 6:
            vlmul = 1/4
        elif vlmul == 7:
            vlmul = 1/2
        else:
            vlmul = 1
        # TODO vlmul determines grouping of vector registers; not yet implemented

        elem_size = vsew // 8

        group_size = vlmul if vlmul > 1 else 1

        # creates groups of registers based on lmul
        reg_groups = {
            base: [ 'v' + str(base + i) for i in range(group_size)]
            for base in range(0, 32, group_size)
            if base + group_size <= 32
            }

        processed_bases = []

        # go through all pinned registers and get content
        for reg in self.pinned_vec_regs:
            elems = []
            reg_name_accumulated = ""
            reg_num = int(reg[1:])
            base_num = reg_num - (reg_num % group_size)
            # check if register group was already processed
            if not base_num in processed_bases:
                # go through group and append registers to each other if multiple registers are in a group
                for reg in reg_groups[base_num]:
                    reg_name_accumulated += '/' + reg
                    reg_bytes = b"".join(get_vector_register_value(reg))
                    for i in range(0, vlenb // elem_size):
                        chunk = reg_bytes[i*elem_size:(i+1)*elem_size]
                        val = int.from_bytes(chunk, "little")
                        elems.append(val)
            # strip first / 
            reg_name_accumulated = reg_name_accumulated[1:] if reg_name_accumulated.startswith('/') else reg_name_accumulated
            # write content of register group
            self.vec_regs_content[reg_name_accumulated] = elems

    def generate_title_bar(self):
        content = "\x1b[47m\x1b[30m" + " "*2
        self.poll_stat_regs()
        val_str = ""
        for reg in self.pinned_stat_regs:
            reg_str = f"{reg}: {int.from_bytes(self.stat_regs_content[reg], 'little')}"
            if(len(reg_str) > self._tui_window.width - 4):
                reg_str = reg_str[:self._tui_window.width - 4] + "..."
            if len(val_str) + len(reg_str) + 3 > self._tui_window.width - 4 and len(self.pinned_stat_regs) > 1:
                val_str += " "*self._tui_window.width-len(val_str)
                val_str += "\n  "
                val_str += reg_str
            elif len(self.pinned_stat_regs) > 1:
                val_str += reg_str
                val_str += " | " if reg != self.pinned_stat_regs[-1] else ""
            else:
                val_str += reg_str

        content += val_str + " "*(self._tui_window.width - 2 - len(val_str) % self._tui_window.width) + "\x1b[0m"
        self.lines = content.splitlines() # title bar lines are always the first lines, so ok to overwrite
        self.lines += ["\n"] # spacer line
    
    def generate_body(self):
        if(not self.pinned_vec_regs):
            self.lines += ["No vector registers pinned. Use the 'pin' command to pin vector registers."]
            return
        self.poll_vec_regs()
        longest_reg = max([len(reg) for key, reg in self.vec_regs_content.items()])

        # get info for masking
        reg_active, reg_group_size = get_masked_result_or_store_src()
        active_elems = get_active_elements()

        # determine amount of digits per element for hex display
        vtype = int.from_bytes(self.stat_regs_content["vtype"], "little")
        vsew = 8 << ((vtype >> 3) & 0b111)
        digits = vsew // 4

        idx_col_width = [len(str(longest_reg)) + 2]
        vec_col_widths = [max(len(str(key)), *(len(str(item)) for item in lst)) for key, lst in self.vec_regs_content.items()] if not self.hex_display else [max(len(str(key)), *(len(f"{item:0{len(hex(item))}x}") for item in lst)) for key, lst in self.vec_regs_content.items()]
        col_widths = idx_col_width + vec_col_widths

        rows = ["  ".join([(" " * col_widths[0])] + [str(reg).center(col_widths[c]) for c, reg in enumerate(self.vec_regs_content.keys())])]
        for r in range(longest_reg):
            row = [("[" + str(r) + "]").center(col_widths[0])]
            for c, (name,reg) in enumerate(self.vec_regs_content.items()):
                val = (str(reg[r]) if not self.hex_display else hex(reg[r])) if r < len(reg) else ""
                reg_number = int(name[1:])
                reg_active_base_number = int(reg_active[1:]) if 'v' in reg_active else None
                cell = val.center(col_widths[c])
                if reg_active_base_number is not None and reg_active_base_number <= reg_number < reg_active_base_number + reg_group_size:
                    # register is part of masked operation
                    element = "v" + str(reg_number)
                    cell = val.center(col_widths[c])
                    active = active_elems[r] if len(active_elems) > r else None # Sometimes index out of bounds
                    if active == 0:
                        # Grey background for inactive element
                        cell = (f"\x1b[100m{val.center(col_widths[c])}\x1b[0m").center(col_widths[c])
                        #cell = (f"\x1b[48;5;236m{val}\x1b[0m").center(col_widths[c])
                row.append(cell)
            rows.append("  ".join(row))
        #rows = [row.center(self._tui_window.width) for row in rows]
        rows = [ansi_center(row, self._tui_window.width) for row in rows]

        self.lines += rows
        self.lines += ["\n"] # spacer line

    def vscroll(self, offset):
        max_offset = max(0, len(self.lines) - self._tui_window.height)
        new_offset = self.scroll_offset + offset
        new_offset = max(0, min(new_offset, max_offset))
        if new_offset != self.scroll_offset:
            self.scroll_offset = new_offset
        self.render()

    def render(self):
        self.generate_title_bar()
        self.generate_body()

        max_offset = max(0, len(self.lines) - self._tui_window.height)
        if self.scroll_offset > max_offset:
            self.scroll_offset = max_offset

        visible = self.lines[self.scroll_offset:self.scroll_offset + self._tui_window.height]
        self._tui_window.write("".join(visible), True)

    def close(self):
        gdb.events.stop.disconnect(self._step_listener)

class PinCommand(gdb.Command):
    """Pin a vector register for display in the TUI window."""

    def __init__(self):
        super(PinCommand, self).__init__("pin", gdb.COMMAND_USER)

    def invoke(self, arg, from_tty):
        if arg == "all":
            VectorWindow.pinned_vec_regs = [f"v{i}" for i in range(32)]
        else:
            if any(char.isdigit() for char in arg):
                # pin vector register
                VectorWindow.pinned_vec_regs.append(arg) if arg not in VectorWindow.pinned_vec_regs else None
                gdb.execute("refresh")
            else:
                # pin status register
                VectorWindow.pinned_stat_regs.append(arg) if arg not in VectorWindow.pinned_stat_regs else None
                gdb.execute("refresh")

class UnpinCommand(gdb.Command):
    """Unpin a vector register for display in the TUI window."""

    def __init__(self):
        super(UnpinCommand, self).__init__("unpin", gdb.COMMAND_USER)

    def invoke(self, arg, from_tty):
        if arg == "all":
            VectorWindow.pinned_vec_regs = []
        else:
            if any(char.isdigit() for char in arg):
                # unpin vector register
                VectorWindow.pinned_vec_regs.remove(arg)
                gdb.execute("refresh")
            else:
                # unpin status register
                VectorWindow.pinned_stat_regs.remove(arg)
                gdb.execute("refresh")

class SwitchHexDisplay(gdb.Command):
    """Toggle hex display for vector register values in the TUI window."""

    def __init__(self):
        super(SwitchHexDisplay, self).__init__("togglehex", gdb.COMMAND_USER)

    def invoke(self, arg, from_tty):
        VectorWindow.hex_display = not VectorWindow.hex_display
        gdb.execute("refresh")

gdb.register_window_type("vectors", VectorWindow)
PinCommand()
UnpinCommand()
SwitchHexDisplay()
