"""Encode an ``itemout.txt`` table back into the binary ``item.bin`` format."""
from __future__ import annotations

import argparse
import pathlib
import struct
from typing import Iterable, List, Tuple

# Column layout requested for decoded item data. The binary provides 25 numeric
# attributes; the list below mirrors the supplied attribute order and is
# trimmed to that count when validating headers.
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

RECORD_SIZE = 236
COUNT_SIZE = 4
NAME_SIZE = 28
ATTR_COUNT = 25
DESC_SIZE = 104
NAME_OFFSET = COUNT_SIZE
ATTR_OFFSET = NAME_OFFSET + NAME_SIZE
DESC_OFFSET = ATTR_OFFSET + ATTR_COUNT * 4

DEFAULT_INPUT = pathlib.Path("itemout.txt")
DEFAULT_OUTPUT = pathlib.Path("item.bin")


class ItemRow:
    """Container for a single item row from ``itemout.txt``."""

    def __init__(self, item_id: int, name: str, attributes: Tuple[int, ...], description: str):
        self.item_id = item_id
        self.name = name
        self.attributes = attributes
        self.description = description


def parse_header(header_line: str) -> List[str]:
    """Return the header column names, validating the expected layout."""

    header = header_line.rstrip("\n").split("\t")

    expected_header = [
        ITEM_ATTRIBUTE_FIELDS[0],  # itemid
        ITEM_ATTRIBUTE_FIELDS[1],  # name
        *ITEM_ATTRIBUTE_FIELDS[2 : 2 + ATTR_COUNT],
        ITEM_ATTRIBUTE_FIELDS[-1],  # description
    ]

    if header != expected_header:
        raise ValueError(
            "Unexpected header in itemout.txt; expected: " + "\t".join(expected_header)
        )

    return header


def parse_rows(lines: Iterable[str]) -> List[ItemRow]:
    """Parse item rows from the remaining file *lines*."""

    items: List[ItemRow] = []
    for line in lines:
        fields = line.rstrip("\n").split("\t")
        if len(fields) != 2 + ATTR_COUNT + 1:  # itemid, name, attributes, description
            raise ValueError(f"Invalid row with {len(fields)} fields: {line!r}")

        item_id = int(fields[0])
        name = fields[1]
        attributes = tuple(int(value) for value in fields[2 : 2 + ATTR_COUNT])
        description = fields[-1]

        items.append(ItemRow(item_id, name, attributes, description))

    return items


def encode_record(item: ItemRow) -> bytes:
    """Encode a single :class:`ItemRow` into its binary representation."""

    record = bytearray(RECORD_SIZE)

    struct.pack_into("<I", record, 0, item.item_id)

    encoded_name = item.name.encode("cp949", errors="replace")[: NAME_SIZE - 1]
    record[NAME_OFFSET : NAME_OFFSET + len(encoded_name)] = encoded_name

    struct.pack_into(f"<{ATTR_COUNT}I", record, ATTR_OFFSET, *item.attributes)

    encoded_desc = item.description.encode("cp949", errors="replace")[: DESC_SIZE - 1]
    record[DESC_OFFSET : DESC_OFFSET + len(encoded_desc)] = encoded_desc

    return bytes(record)


def encode_items(items: Iterable[ItemRow]) -> bytes:
    """Serialize *items* into the ``item.bin`` binary layout."""

    items_list = list(items)
    output = bytearray(COUNT_SIZE + len(items_list) * RECORD_SIZE)

    struct.pack_into("<I", output, 0, len(items_list))
    for index, item in enumerate(items_list):
        start = COUNT_SIZE + index * RECORD_SIZE
        output[start : start + RECORD_SIZE] = encode_record(item)

    return bytes(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Encode itemout.txt back into item.bin")
    parser.add_argument("input", nargs="?", type=pathlib.Path, default=DEFAULT_INPUT, help="Source itemout.txt file")
    parser.add_argument("output", nargs="?", type=pathlib.Path, default=DEFAULT_OUTPUT, help="Destination item.bin path")
    args = parser.parse_args()

    lines = args.input.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("Input file is empty")

    total_items = int(lines[0])
    header = parse_header(lines[1])
    _ = header  # appease linters if unused
    items = parse_rows(lines[2:])

    if total_items != len(items):
        raise ValueError(
            f"Item count mismatch: header shows {total_items}, but {len(items)} rows were found"
        )

    args.output.write_bytes(encode_items(items))


if __name__ == "__main__":
    main()
