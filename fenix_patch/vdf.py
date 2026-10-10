# SPDX-License-Identifier: MIT
"""Minimal, position-preserving edits of Steam's config.vdf.

Only the simulator's compatibility-tool entry is touched; every other byte is
kept. Anything this small parser does not understand is rejected, so the file
is then left alone.
"""
import re

from .core import PatchError

TOKEN = re.compile(r'(?:\s|//[^\n]*)*(?:"((?:[^"\\]|\\.)*)"|([{}]))')
STEAM = ("InstallConfigStore", "Software", "Valve", "Steam")
MAPPING = "CompatToolMapping"


class Block:
    def __init__(self, entries, start, close, end):
        self.entries, self.start, self.close, self.end = entries, start, close, end

    def find(self, key):
        found = [entry for entry in self.entries if entry[0].lower() == key.lower()]
        if len(found) > 1:
            raise PatchError("Steam's configuration has duplicate entries: " + key)
        return found[0] if found else None


def _entries(text, position, top):
    entries = []
    while True:
        match = TOKEN.match(text, position)
        if not match:
            if top and not text[position:].strip():
                return entries, len(text), len(text)
            raise PatchError("Steam's configuration could not be read.")
        if match.group(2) == "}" and not top:
            return entries, match.start(2), match.end()
        if match.group(2):
            raise PatchError("Steam's configuration could not be read.")
        key, start = match.group(1), match.start(1) - 1
        match = TOKEN.match(text, match.end())
        if not match or match.group(2) == "}":
            raise PatchError("Steam's configuration could not be read.")
        if match.group(2) == "{":
            inner, close, position = _entries(text, match.end(), False)
            value = Block(inner, match.end(), close, position)
        else:
            value, position = match.group(1), match.end()
        entries.append((key, value, start, position))


def parse(text):
    entries, _, _ = _entries(text, 0, True)
    return Block(entries, 0, len(text), len(text))


def plain(block):
    return [(key, plain(value) if isinstance(value, Block) else value) for key, value, _, _ in block.entries]


def steam_block(root):
    block = root
    for key in STEAM:
        entry = block.find(key)
        if entry is None or not isinstance(entry[1], Block):
            raise PatchError("Steam's configuration has an unexpected layout.")
        block = entry[1]
    return block


def mapping_block(root):
    entry = steam_block(root).find(MAPPING)
    if entry is not None and not isinstance(entry[1], Block):
        raise PatchError("Steam's configuration has an unexpected layout.")
    return entry[1] if entry else None


def compat_tool(text, appid):
    """The forced compatibility tool for one application, or None."""
    mapping = mapping_block(parse(text))
    entry = mapping.find(appid) if mapping else None
    if entry is None or not isinstance(entry[1], Block):
        return None
    name = entry[1].find("name")
    return name[1] if name and isinstance(name[1], str) and name[1] else None


def _line_start(text, position):
    start = text.rfind("\n", 0, position) + 1
    if text[start:position].strip():
        raise PatchError("Steam's configuration has an unexpected layout.")
    return start


def _without(text, appid):
    """Structure with this application's entry (and an emptied mapping) left out."""
    def strip(items, path):
        result = []
        for key, value in items:
            if isinstance(value, list):
                here = path + (key.lower(),)
                steam = tuple(part.lower() for part in STEAM)
                if here == steam + (MAPPING.lower(), appid):
                    continue
                value = strip(value, here)
                if here == steam + (MAPPING.lower(),) and not value:
                    continue
            result.append((key, value))
        return result
    return strip(plain(parse(text)), ())


def set_compat_tool(text, appid, tool):
    """Force `tool` for `appid`; with tool None, remove the application's entry."""
    if not re.fullmatch(r"\d+", appid) or (tool is not None and not re.fullmatch(r"[A-Za-z0-9._ -]+", tool)):
        raise PatchError("Invalid compatibility tool selection")
    root = parse(text)
    steam = steam_block(root)
    mapping = mapping_block(root)
    newline = "\r\n" if "\r\n" in text else "\n"
    def entry(depth):
        tabs = "\t" * depth
        return newline.join((tabs + '"%s"' % appid, tabs + "{", tabs + '\t"name"\t\t"%s"' % tool,
                             tabs + '\t"config"\t\t""', tabs + '\t"priority"\t\t"250"', tabs + "}")) + newline
    depth = len(STEAM) + 1
    existing = mapping.find(appid) if mapping else None
    if existing and tool is None and len(mapping.entries) == 1:
        # Leave no empty mapping behind when the only entry goes.
        existing = steam.find(MAPPING)
    if existing:
        start = _line_start(text, existing[2])
        end = text.index("\n", existing[3] - 1) + 1 if "\n" in text[existing[3] - 1:] else len(text)
        result = text[:start] + (entry(depth) if tool else "") + text[end:]
    elif tool is None:
        return text
    elif mapping:
        start = _line_start(text, mapping.close)
        result = text[:start] + entry(depth) + text[start:]
    else:
        start = _line_start(text, steam.close)
        tabs = "\t" * (depth - 1)
        result = text[:start] + tabs + '"%s"' % MAPPING + newline + tabs + "{" + newline + entry(depth) + \
            tabs + "}" + newline + text[start:]
    # Everything else must be exactly what Steam wrote.
    if _without(result, appid) != _without(text, appid) or compat_tool(result, appid) != tool:
        raise PatchError("Steam's configuration could not be changed safely; select the tool in Steam instead.")
    return result
