"""Merge an NPU .po file into a compiled Cemu gettext catalog.

    python i18n/npu/merge_catalog.py bin/resources/ko/cemu.mo i18n/npu/ko.po

Every message already in the catalog is kept; the .po translations are added
or replace the same msgid. The catalog is rewritten in place, sorted, without a
hash table (gettext and wxWidgets both read that layout).
"""
import ast
import struct
import sys

MAGIC = 0x950412DE


def read_mo(path):
    data = open(path, "rb").read()
    if struct.unpack("<I", data[:4])[0] != MAGIC:
        raise SystemExit(f"{path}: not a little-endian .mo file")
    count, originals, translations = struct.unpack("<3I", data[8:20])
    def strings(table):
        for i in range(count):
            length, offset = struct.unpack("<2I", data[table + 8 * i:table + 8 * i + 8])
            yield data[offset:offset + length]
    return dict(zip(strings(originals), strings(translations)))


def read_po(path):
    """Single-form entries, one quoted line or several, no msgctxt."""
    entries, key, current = {}, None, None
    def flush():
        if key is not None and key[0] and key[1]:
            entries[key[0].encode()] = key[1].encode()
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line.startswith("msgid "):
            flush()
            key, current = ["", ""], 0
            line = line[len("msgid "):]
        elif line.startswith("msgstr "):
            current = 1
            line = line[len("msgstr "):]
        elif not line.startswith('"'):
            continue
        key[current] += ast.literal_eval(line)
    flush()
    return entries


def write_mo(path, messages):
    keys = sorted(messages)
    header = 7 * 4
    originals = header
    translations = originals + 8 * len(keys)
    offset = translations + 8 * len(keys)
    table, blob = [], b""
    for source in (keys, [messages[k] for k in keys]):
        for text in source:
            table.append((len(text), offset + len(blob)))
            blob += text + b"\0"
    with open(path, "wb") as out:
        out.write(struct.pack("<7I", MAGIC, 0, len(keys), originals, translations, 0, offset))
        for length, start in table:
            out.write(struct.pack("<2I", length, start))
        out.write(blob)


if __name__ == "__main__":
    catalog, po = sys.argv[1:3]
    messages = read_mo(catalog)
    added = read_po(po)
    messages.update(added)
    write_mo(catalog, messages)
    print(f"{catalog}: {len(messages)} messages, {len(added)} from {po}")
