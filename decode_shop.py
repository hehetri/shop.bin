"""Utility to convert the encrypted ``shop.bin`` data between formats.

The original 2015 script used a ``convertway`` flag with three modes:

``convertway == 1``
    Read an already decoded binary (``shop_decoded.bin``) and emit ``shopout.txt``.

``convertway == 2``
    Read ``shopout.txt`` and rebuild a decoded binary (``shop_decoded.bin``).
    A template header from an existing binary is preserved when available.

``convertway == 3``
    Read the encrypted ``shop.bin``, decode it, and emit ``shopout.txt``.

This module exposes equivalent behavior through a tidy CLI while keeping the
fixed-width record layout used by the game data.
"""
from __future__ import annotations

import argparse
import pathlib
import struct
from typing import Iterable, List, Sequence, Tuple

RECORD_SIZE = 108
HEADER_SKIP = 26
COUNT_SIZE = 4
DEFAULT_ENCRYPTED = pathlib.Path("shop.bin")
DEFAULT_DECODED = pathlib.Path("shop_decoded.bin")
DEFAULT_TEXT = pathlib.Path("shopout.txt")


def decode_bytes(data: bytes) -> bytes:
    """Return the bitwise-not decoding of *data* (XOR with ``0xFF``)."""

    return bytes((~b) & 0xFF for b in data)


def encode_bytes(data: bytes) -> bytes:
    """Return the bitwise-not encoding of *data* (XOR with ``0xFF``)."""

    return decode_bytes(data)


def parse_records(blob: bytes) -> Tuple[int, List[Tuple[int, ...]]]:
    """Parse a decoded binary *blob* and return a count and record tuples."""

    total_items = struct.unpack_from("<I", blob, HEADER_SKIP)[0]
    records: List[Tuple[int, ...]] = []
    offset = HEADER_SKIP + COUNT_SIZE

    for index in range(total_items):
        start = offset + index * RECORD_SIZE
        record = blob[start : start + RECORD_SIZE]

        tab = record[0]
        subtab = record[1]
        main_items = struct.unpack_from("<4I", record, 2)
        name = record[18:44].decode("cp949").rstrip("\x00")

        options = struct.unpack_from("<10I", record, 64)
        sale_new = struct.unpack_from("<I", record, 104)[0]

        records.append(
            (
                tab,
                subtab,
                main_items[0],
                main_items[1],
                main_items[2],
                main_items[3],
                name,
                *options[:9],
                sale_new,
            )
        )

    return total_items, records


def write_output(path: pathlib.Path, total_items: int, records: Iterable[Tuple[int, ...]]):
    """Write the unpacked *records* to ``path`` in the expected layout."""

    header = (
        "tab\tsubtab\tmainitem\tshowoption1\tshowoption2\tshowoption3\t"
        "itemname\toption1\toption2\toption3\toption4\toption5\toption6\t"
        "option7\toption8\toption9\tsale/new\n"
    )

    with path.open("w", encoding="cp949") as outf:
        outf.write(f"{total_items}\n")
        outf.write(header)
        for rec in records:
            tab, subtab, mainitem, show1, show2, show3, name, *rest = rec
            options = rest[:-1]
            sale_flag = rest[-1]
            line = (
                f"{tab}\t{subtab}\t{mainitem}\t{show1}\t{show2}\t{show3}\t"
                f"{name}\t" + "\t".join(str(opt) for opt in options) + f"\t{sale_flag}\n"
            )
            outf.write(line)


def read_text_records(path: pathlib.Path) -> Tuple[int, List[Tuple[int, ...]]]:
    """Read ``shopout.txt`` style text and return a count and records."""

    lines = path.read_text(encoding="cp949").splitlines()
    if not lines:
        raise ValueError("Input text file is empty")

    total_items = int(lines[0])
    records: List[Tuple[int, ...]] = []

    for line in lines[2:]:
        if not line.strip():
            continue

        parts: List[str] = line.split("\t")
        if len(parts) != 17:
            raise ValueError(f"Unexpected column count in line: {line}")

        tab, subtab, mainitem, show1, show2, show3 = map(int, parts[:6])
        name = parts[6]
        options = list(map(int, parts[7:16]))
        sale_flag = int(parts[16])
        records.append(
            (
                tab,
                subtab,
                mainitem,
                show1,
                show2,
                show3,
                name,
                *options,
                sale_flag,
            )
        )

    if total_items != len(records):
        raise ValueError(
            f"Item count mismatch: header says {total_items}, file contains {len(records)}"
        )

    return total_items, records


def build_record_bytes(record: Sequence[int | str]) -> bytes:
    """Pack a single record tuple back into binary form."""

    (
        tab,
        subtab,
        mainitem,
        show1,
        show2,
        show3,
        name,
        *rest,
    ) = record

    options = list(rest[:-1])
    sale_flag = int(rest[-1])

    name_bytes = str(name).encode("cp949", errors="replace")[:26].ljust(26, b"\x00")
    reserved = b"\x00" * 20
    padded_options = options + [0] * (10 - len(options))

    return b"".join(
        [
            struct.pack("<B", int(tab)),
            struct.pack("<B", int(subtab)),
            struct.pack("<4I", int(mainitem), int(show1), int(show2), int(show3)),
            name_bytes,
            reserved,
            struct.pack("<10I", *map(int, padded_options[:10])),
            struct.pack("<I", sale_flag),
        ]
    )


def build_binary_blob(
    template_header: bytes, total_items: int, records: Iterable[Tuple[int, ...]]
) -> bytes:
    """Construct a decoded binary blob from *records* using *template_header*."""

    header = template_header[:HEADER_SKIP].ljust(HEADER_SKIP, b"\x00")
    payload = b"".join(build_record_bytes(rec) for rec in records)
    return header + struct.pack("<I", total_items) + payload


def convert_plain_to_text(decoded_path: pathlib.Path, text_path: pathlib.Path) -> None:
    total_items, records = parse_records(decoded_path.read_bytes())
    write_output(text_path, total_items, records)


def convert_text_to_plain(
    text_path: pathlib.Path, decoded_path: pathlib.Path, template: pathlib.Path | None
) -> None:
    total_items, records = read_text_records(text_path)
    header_source = template if template and template.exists() else decoded_path
    header_bytes = b""
    if header_source.exists():
        header_bytes = header_source.read_bytes()[:HEADER_SKIP]

    blob = build_binary_blob(header_bytes, total_items, records)
    decoded_path.write_bytes(blob)


def convert_encrypted_to_text(
    encrypted_path: pathlib.Path, text_path: pathlib.Path
) -> None:
    decoded = decode_bytes(encrypted_path.read_bytes())
    total_items, records = parse_records(decoded)
    write_output(text_path, total_items, records)


def main():
    parser = argparse.ArgumentParser(description="Convert shop.bin data between formats.")
    parser.add_argument(
        "mode",
        choices=["1", "2", "3"],
        help=(
            "1: decoded binary -> text, 2: text -> decoded binary, "
            "3: encrypted binary -> text"
        ),
    )
    parser.add_argument(
        "--input",
        type=pathlib.Path,
        help="Input file (defaults vary by mode)",
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        help="Output file (defaults vary by mode)",
    )
    parser.add_argument(
        "--template",
        type=pathlib.Path,
        default=None,
        help="Optional template binary to copy the header from when rebuilding",
    )

    args = parser.parse_args()

    if args.mode == "1":
        decoded = args.input or DEFAULT_DECODED
        text = args.output or DEFAULT_TEXT
        convert_plain_to_text(decoded, text)
    elif args.mode == "2":
        text = args.input or DEFAULT_TEXT
        decoded = args.output or DEFAULT_DECODED
        convert_text_to_plain(text, decoded, args.template)
    else:  # args.mode == "3"
        encrypted = args.input or DEFAULT_ENCRYPTED
        text = args.output or DEFAULT_TEXT
        convert_encrypted_to_text(encrypted, text)


if __name__ == "__main__":
    main()
