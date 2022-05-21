#-------------------------------------------------------------------------------
# elftools example: elf_notes.py
#
# An example of obtaining note sections from an ELF file and examining
# the notes it contains.
#
# Eli Bendersky (eliben@gmail.com)
# This code is in the public domain
#-------------------------------------------------------------------------------
from __future__ import print_function
import sys

# If pyelftools is not installed, the example can also run from the root or
# examples/ dir of the source distribution.
sys.path[0:0] = ['.', '..']

from elftools.elf.elffile import ELFFile
from elftools.elf.sections import NoteSection
from elftools.common.py3compat import bytes2hex
from elftools.elf.sections import SymbolTableSection
from elftools.elf.relocation import RelocationSection

import networkx as nx
import pathlib

IGNORE_SECTIONS = [".group", ".debug_macro", ".debug_info", ".debug_abbrev", ".debug_loc", ".debug_aranges", ".debug_frame", ".debug_line", ".debug_ranges", ".comment", ".debug_str", ".riscv.attributes"]
IGNORE_RELA_SECTIONS = [".rela" + s for s in IGNORE_SECTIONS]
IGNORE_SECTIONS += IGNORE_RELA_SECTIONS

def symbol_to_node(filename, symbol):
    bind = symbol["st_info"]["bind"]
    attrs = {"label": symbol.name, "size_bytes": symbol["st_size"]}
    if symbol["st_shndx"] != "SHN_UNDEF":
        attrs["source_file"] = str(filename)
    if bind == "STB_LOCAL":
        attrs["bind"] = "local"
        source_symbol_name = f"{filename}:{symbol.name}"
    elif bind == "STB_GLOBAL":
        attrs["bind"] = "global"
        source_symbol_name = f"{symbol.name}"
    elif bind == "STB_WEAK":
        attrs["bind"] = "weak"
        source_symbol_name = f"{symbol.name}"
    return source_symbol_name, attrs

def get_string_node(filename, data, offset):
    end = offset
    while data[end] != 0:
        end += 1
    attrs = {"source_file": str(filename)}
    if end == offset:
        key = "empty_string"
        decoded = "''"
    else:
        decoded = data[offset:end].decode("utf-8")
        key = repr(decoded).strip("\"'")
    attrs["label"] = key
    attrs["size_bytes"] = end - offset
    return f"{filename}:{key}", attrs

def process_file(filename, graph):
    with open(filename, 'rb') as f:
        ef = ELFFile(f)
        # Load undefined symbols
        symtab = ef.get_section_by_name(".symtab")
        symbols = list(symtab.iter_symbols())
        symbols_by_section = {}
        for s in symbols:
            si = s["st_shndx"]
            bind = s["st_info"]["bind"]
            if s.name and bind == "STB_GLOBAL" and si != "SHN_UNDEF":
                node_name, node_attrs = symbol_to_node(filename, s)
                graph.add_node(node_name, **node_attrs)
            if si not in symbols_by_section:
                symbols_by_section[si] = []
            symbols_by_section[si].append(s)

        for i, sect in enumerate(ef.iter_sections()):
            if sect.name in IGNORE_SECTIONS:
                continue
            # print(i, sect.name, sect.header["sh_type"], hex(sect.header["sh_size"]))
            if i in symbols_by_section:
                if sect.name.startswith(".sdata"):
                    other_names = {}
                    for s in symbols_by_section[i]:
                        if not s.name:
                            continue
                        offset = s["st_value"]
                        if s["st_size"] == 0:
                            if offset not in other_names:
                                other_names[offset] = []
                            node_name, node_attrs = symbol_to_node(filename, s)
                            graph.add_node(node_name, **node_attrs)
                            other_names[offset].append(node_name)
                        else:
                            actual_node_name, node_attrs = symbol_to_node(filename, s)
                            graph.add_node(actual_node_name, **node_attrs)
                            if offset in other_names:
                                for other_name in other_names[offset]:
                                    graph.add_edge(actual_node_name, other_name)
            if sect.name.startswith(".rodata") and ".str" in sect.name:
                for s in symbols_by_section[i]:
                    if not s.name:
                        continue
                    symbol_node, symbol_attrs = symbol_to_node(filename, s)
                    graph.add_node(symbol_node, **symbol_attrs)
                    string_node, string_attrs = get_string_node(filename, sect.data(), s["st_value"])
                    graph.add_node(string_node, **string_attrs)
                    graph.add_edge(symbol_node, string_node)
            if isinstance(sect, RelocationSection):
                source_symbol_name = None
                target_section = sect.header["sh_info"]
                for s in symbols_by_section[target_section]:
                    if s["st_size"] == 0:
                        continue
                    source_symbol_name, symbol_attrs = symbol_to_node(filename, s)
                    graph.add_node(source_symbol_name, **symbol_attrs)

                for r in sect.iter_relocations():
                    if r["r_info_sym"] == 0:
                        continue
                    s = symbols[r["r_info_sym"]]
                    if s["st_shndx"] == target_section:
                        continue
                    dest_symbol_name, symbol_attrs = symbol_to_node(filename, s)
                    graph.add_node(dest_symbol_name, **symbol_attrs)
                    graph.add_edge(source_symbol_name, dest_symbol_name)

def process_map_file(filename, graph):
    path = pathlib.Path(filename)
    top = path.parent.parent
    with open(filename, "r") as f:
        for line in f:
            if line.startswith("LOAD"):
                fn = pathlib.Path(line[5:].strip())
                if not fn.is_absolute():
                    fn = top / fn
                print(fn.resolve())
                try:
                    process_file(fn, graph)
                except BaseException as e:
                    print(e)

if __name__ == '__main__':
    graph = nx.DiGraph()
    if sys.argv[1].endswith(".o"):
        for filename in sys.argv[1:]:
            process_file(filename, graph)
    elif sys.argv[1].endswith(".map"):
        process_map_file(sys.argv[1], graph)
    a = nx.nx_agraph.to_agraph(graph)

    nx.write_gexf(graph, "test.gexf")

    # Add clusters
    nodes_by_file = {}
    for node, filename in graph.nodes(data="source_file"):
        if not filename:
            continue
        if filename not in nodes_by_file:
            nodes_by_file[filename] = set()
        nodes_by_file[filename].add(node)

    for filename in nodes_by_file:
        a.add_subgraph(nodes_by_file[filename], "cluster" + str(filename), label=filename, color="azure", style="filled")
    a.write("test.dot")
