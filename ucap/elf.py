"""ELF symbol resolution and listing."""

import contextlib
import io
import logging
import pathlib
import re
import sys

from ucap.config import Config
from ucap.constants import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)
logging.getLogger('elfwrapper').setLevel(logging.WARNING)


def _load_elf(elf_path):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()):
        from elfwrapper.elf_wrapper import ElfAddrObj
        return ElfAddrObj(elf_path)


def resolve_symbol_address(cfg: Config):
    elf = None
    for var in cfg.pre_vars + cfg.vars + cfg.post_vars:
        if isinstance(var.address, str):
            if cfg.elf_file is None:
                logger.error(
                    f"elf_file is required to resolve the address of symbol '{var.address}'"
                )
                sys.exit(1)
            else:
                if elf is None:
                    logger.info("loading elf file")
                    elf_path = pathlib.Path(
                        cfg.elf_file).expanduser().resolve()
                    if not elf_path.exists() or not elf_path.is_file():
                        logger.error(
                            f"'{cfg.elf_file}' not exists or is not file")
                        sys.exit(1)
                    elf = _load_elf(elf_path)
            try:
                addr = elf.get_var_addrs(var.address)
                logger.info(f"resolved symbol '{var.address}' -> 0x{addr:X}")
                var.address = addr
            except Exception as e:
                logger.error(f"symbol '{var.address}' not found: {e}")
                sys.exit(1)

    return elf


def list_symbols(elf_path: str, pattern: str | None):
    obj = _load_elf(elf_path)
    var_names = sorted(obj.variables_dict,
                       key=lambda n: obj.symbol_dict.get(n, 0))

    entries: list[tuple[int, str, str]] = []

    for name in var_names:
        addr = obj.symbol_dict.get(name)
        if addr is None:
            continue

        var_attrs = obj.variables_dict[name]
        type_name = _resolve_type_name(obj, var_attrs.get('DW_AT_type'))
        entries.append((addr, type_name or '', name))

        _walk_members(obj, name, addr,
                       var_attrs.get('DW_AT_type'), entries, 10)

    if pattern:
        compiled = re.compile(pattern)
        entries = [e for e in entries if compiled.search(e[2])]

    if not entries:
        logger.info('no symbols matched')
        return

    for addr, ty, sym in entries:
        print(f'0x{addr:08X} {ty:>20} {sym}')


_MAX_ARRAY_ELEMS = 4


def _walk_members(obj, prefix, base_addr, type_offset, entries,
                   depth: int):
    if type_offset is None or depth <= 0:
        return

    type_off = _follow_typedef(obj, type_offset)
    if type_off is None:
        return

    ta = obj.offset_dict.get(type_off)
    if ta is None:
        return

    tag = ta.get('tag', '')

    if tag in ('DW_TAG_structure_type', 'DW_TAG_class_type'):
        sname = ta.get('DW_AT_name') or type_off
        if sname not in obj.struct_dict:
            return
        members = obj.struct_dict[sname]
        for mname, mattrs in members.items():
            moff = _parse_member_offset(
                mattrs.get('DW_AT_data_member_location'))
            if moff is None:
                continue
            madr = base_addr + moff
            mtype = mattrs.get('DW_AT_type')
            full_name = f'{prefix}.{mname}'
            type_name = _resolve_type_name(obj, mtype)
            entries.append((madr, type_name or '', full_name))
            _walk_members(obj, full_name, madr, mtype, entries,
                           depth - 1)

    elif tag == 'DW_TAG_union_type':
        members = obj.union_dict.get(type_off)
        if not members:
            return
        for member in members:
            if member.get('tag') != 'DW_TAG_member':
                continue
            mname = member.get('DW_AT_name')
            if not mname:
                continue
            mtype = member.get('DW_AT_type')
            full_name = f'{prefix}.{mname}'
            type_name = _resolve_type_name(obj, mtype)
            entries.append((base_addr, type_name or '', full_name))
            _walk_members(obj, full_name, base_addr, mtype, entries,
                           depth - 1)

    elif tag == 'DW_TAG_array_type':
        arr_info = obj.array_type_dict.get(type_off)
        if arr_info is None:
            return
        elem_type = arr_info.get('DW_AT_type')
        if elem_type is None:
            return
        ubounds = arr_info.get('DW_AT_upper_bound', [])
        count = (ubounds[0] + 1) if ubounds else 1
        for i in range(min(count, _MAX_ARRAY_ELEMS)):
            full_name = f'{prefix}[{i}]'
            type_name = _resolve_type_name(obj, elem_type)
            elem_addr = base_addr + _elem_size(obj, elem_type) * i
            entries.append((elem_addr, type_name or '', full_name))
            _walk_members(obj, full_name, elem_addr, elem_type, entries,
                           depth - 1)


def _elem_size(obj, type_offset):
    type_off = _follow_typedef(obj, type_offset)
    if type_off is None:
        return 0
    ta = obj.offset_dict.get(type_off)
    if ta is None:
        return 0

    bs = ta.get('DW_AT_byte_size')
    if bs is not None:
        try:
            return int(bs)
        except (ValueError, TypeError):
            pass
    return 0


def _follow_typedef(obj, type_offset):
    seen = set()
    while type_offset not in seen and type_offset is not None:
        seen.add(type_offset)
        ta = obj.offset_dict.get(type_offset)
        if ta is None:
            return None
        tag = ta.get('tag', '')
        if tag not in ('DW_TAG_typedef', 'DW_TAG_volatile_type',
                        'DW_TAG_const_type', 'DW_TAG_restrict_type',
                        'DW_TAG_atomic_type'):
            return type_offset
        type_offset = ta.get('DW_AT_type')
    return None



def _resolve_type_name(obj, type_offset: int | None) -> str | None:
    if type_offset is None:
        return None
    seen = set()
    while type_offset not in seen:
        seen.add(type_offset)
        type_attrs = obj.offset_dict.get(type_offset)
        if type_attrs is None:
            return None
        tag = type_attrs.get('tag', '')
        name = type_attrs.get('DW_AT_name')
        if tag in ('DW_TAG_base_type', 'DW_TAG_typedef',
                    'DW_TAG_structure_type', 'DW_TAG_class_type',
                    'DW_TAG_enumeration_type'):
            if name:
                return name
        next_offset = type_attrs.get('DW_AT_type')
        if next_offset is None:
            if tag in ('DW_TAG_pointer_type', 'DW_TAG_ptr_to_member_type'):
                name = type_attrs.get('DW_AT_name')
                return name if name else 'ptr'
            return name if name else tag.replace('DW_TAG_', '')
        type_offset = next_offset
    return None


def _parse_member_offset(loc: str | None) -> int | None:
    if loc is None:
        return None
    m = re.search(r'DW_OP_plus_uconst:\s*(\d+)', loc)
    if m:
        return int(m.group(1))
    m = re.search(r'\b(\d+)\b', loc)
    return int(m.group(1)) if m else None
