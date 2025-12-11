"""Utility to unpack the encrypted ``shop.bin`` file to a tab-separated text file.

The game file is stored with every byte bitwise inverted (XOR 0xFF). This script
undoes the inversion, parses the fixed-width records, and writes a human-readable
``shopout.txt`` that follows the column layout shown in the recovered snippet.
"""
from __future__ import annotations

import argparse
import pathlib
import struct
from typing import Iterable, Tuple

# Mirror the attribute naming requested for item decoding so both scripts share
# the same field definitions where applicable.
ITEM_ATTRIBUTE_FIELDS = [
    "itemid",
    "name",
    "level",
    "unk",
    "price",
    "pricec",
    "sell",
    "unk",
    "unk",
    "durtype",
    "duration",
    "hp",
    "attmin",
    "attmax",
    "att(trans)min",
    "att(trans)max",
    "TransGauge",
    "Crit",
    "evade",
    "spectrans",
    "speed",
    "transbotdef",
    "transbotatt",
    "transspeed",
    "ranged",
    "luck",
    "unk",
    "effect",
    "image",
    "description",
]

RECORD_SIZE = 108
HEADER_SKIP = 26
COUNT_SIZE = 4
DEFAULT_INPUT = pathlib.Path("shop.bin")
DEFAULT_OUTPUT = pathlib.Path("shopout.txt")


def decode_bytes(data: bytes) -> bytes:
    """Return the bitwise-not decoding of *data* (XOR with ``0xFF``).

    The encrypted ``shop.bin`` simply inverts every byte. ``shop_decoded.bin`` in
    the repository is the already inverted form, but this helper allows us to
    start directly from the encrypted source.
    """

    return bytes((~b) & 0xFF for b in data)


def parse_records(blob: bytes) -> Tuple[int, Iterable[Tuple[int, ...]]]:
    """Parse the decoded binary *blob*.

    Returns a tuple containing the number of records and an iterator of record
    tuples with the following layout:

    ``(tab, subtab, mainitem, show1, show2, show3, name, options..., sale_new)``
    """

    total_items = struct.unpack_from("<I", blob, HEADER_SKIP)[0]
    records = []
    offset = HEADER_SKIP + COUNT_SIZE

    for index in range(total_items):
        start = offset + index * RECORD_SIZE
        record = blob[start : start + RECORD_SIZE]

        tab = record[0]
        subtab = record[1]
        main_items = struct.unpack_from("<4I", record, 2)
        name = record[18:44].decode("cp949").rstrip("\x00")

        # The next 20 bytes are zero-filled in the sample data; they appear to
        # be reserved flags. We skip them but leave the slice here for clarity.
        _reserved_flags = record[44:64]

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


def main():
    parser = argparse.ArgumentParser(description="Unpack the encrypted shop.bin file.")
    parser.add_argument("input", nargs="?", type=pathlib.Path, default=DEFAULT_INPUT, help="Path to shop.bin")
    parser.add_argument("output", nargs="?", type=pathlib.Path, default=DEFAULT_OUTPUT, help="Destination shopout.txt")
    args = parser.parse_args()

    raw_data = args.input.read_bytes()
    decoded = decode_bytes(raw_data)
    total_items, records = parse_records(decoded)
    write_output(args.output, total_items, records)


if __name__ == "__main__":
    main()
