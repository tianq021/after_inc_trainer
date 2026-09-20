#!/usr/bin/env python3
"""Disassemble named IL2CPP methods and annotate calls/RIP-relative globals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / ".analysis_deps"))

import pefile  # type: ignore[import-not-found]  # noqa: E402
from capstone import CS_ARCH_X86, CS_MODE_64, Cs  # type: ignore[import-not-found]  # noqa: E402
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP  # type: ignore[import-not-found]  # noqa: E402


DEFAULT_DLL = Path(r"F:\SteamLibrary\steamapps\common\After Inc\GameAssembly.dll")
DEFAULT_SCRIPT = PROJECT_ROOT / "il2cpp_dump" / "build_24931318" / "script.json"


def load_methods(path: Path) -> tuple[dict[str, list[int]], dict[int, list[str]], list[int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    by_name: dict[str, list[int]] = {}
    by_rva: dict[int, list[str]] = {}
    for item in payload["ScriptMethod"]:
        rva = int(item["Address"])
        name = str(item["Name"])
        by_name.setdefault(name, []).append(rva)
        by_rva.setdefault(rva, []).append(name)
    return by_name, by_rva, sorted(by_rva)


def containing_section(pe: pefile.PE, rva: int) -> str:
    section = pe.get_section_by_rva(rva)
    if section is None:
        return "outside-image"
    return section.Name.rstrip(b"\0").decode("ascii", errors="replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", type=Path, default=DEFAULT_DLL)
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument("--method", action="append", default=[])
    parser.add_argument("--rva", action="append", default=[])
    parser.add_argument("--max-bytes", type=lambda value: int(value, 0), default=0x2000)
    args = parser.parse_args()

    by_name, by_rva, addresses = load_methods(args.script)
    requested: list[tuple[str, int]] = []
    for needle in args.method:
        matches = [(name, rva) for name, rvas in by_name.items() if needle in name for rva in rvas]
        if not matches:
            raise SystemExit(f"No method contains {needle!r}")
        requested.extend(matches)
    for value in args.rva:
        rva = int(value, 0)
        requested.append((" | ".join(by_rva.get(rva, ["manual RVA"])), rva))
    if not requested:
        raise SystemExit("Specify at least one --method or --rva")

    pe = pefile.PE(str(args.dll), fast_load=True)
    image_base = int(pe.OPTIONAL_HEADER.ImageBase)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    seen: set[int] = set()
    for requested_name, rva in requested:
        if rva in seen:
            continue
        seen.add(rva)
        next_rva = next((address for address in addresses if address > rva), rva + args.max_bytes)
        size = min(args.max_bytes, max(1, next_rva - rva))
        offset = pe.get_offset_from_rva(rva)
        code = pe.__data__[offset : offset + size]
        print(f"\n===== {requested_name} RVA 0x{rva:X} size<=0x{size:X} =====")
        for instruction in md.disasm(code, image_base + rva):
            annotations: list[str] = []
            for operand in instruction.operands:
                if operand.type == X86_OP_IMM and instruction.group(2):  # CS_GRP_CALL
                    target_rva = int(operand.imm) - image_base
                    names = by_rva.get(target_rva)
                    annotations.append(
                        f"call RVA 0x{target_rva:X}" + (f" {' | '.join(names)}" if names else "")
                    )
                elif operand.type == X86_OP_MEM and operand.mem.base == X86_REG_RIP:
                    target_va = instruction.address + instruction.size + operand.mem.disp
                    target_rva = target_va - image_base
                    annotations.append(
                        f"RIP=>RVA 0x{target_rva:X} [{containing_section(pe, target_rva)}]"
                    )
            suffix = f" ; {'; '.join(annotations)}" if annotations else ""
            address_rva = instruction.address - image_base
            print(f"0x{address_rva:08X}  {instruction.mnemonic:8s} {instruction.op_str}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
