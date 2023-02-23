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
import arpy

IGNORE_SECTIONS = [".group", ".debug_macro", ".debug_info", ".debug_abbrev", ".debug_loc", ".debug_aranges", ".debug_frame", ".debug_line", ".debug_ranges", ".comment", ".debug_str", ".riscv.attributes", ".debug_rnglists", ".debug_loclists"]
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

def section_to_node(filename, section):
    return filename + section.name, {"label": "rodata", "bind": "local"}

def get_string_node(filename, data, offset):
    end = offset
    while data[end] != 0:
        end += 1
    attrs = {"source_file": str(filename)}
    if end == offset:
        key = "empty_string"
        decoded = "''"
    else:
        decoded = data[offset:end]
        try:
            decoded = decoded.decode("utf-8")
        except UnicodeDecodeError:
            pass
        key = repr(decoded).strip("\"'")
    attrs["label"] = key
    attrs["size_bytes"] = end - offset
    return f"{filename}:{key}", attrs

def process_object_file(f, filename, graph, discarded=set()):
    ef = ELFFile(f)
    # Load undefined symbols
    symtab = ef.get_section_by_name(".symtab")
    if not symtab:
        return
    symbols = list(symtab.iter_symbols())
    sections = list(ef.iter_sections())
    symbols_by_section = {}
    for symbol_index, s in enumerate(symbols):
        si = s["st_shndx"]
        bind = s["st_info"]["bind"]
        stype = s["st_info"]["type"]
        if s.name and bind == "STB_GLOBAL" and si != "SHN_UNDEF":
            if si not in ("SHN_COMMON",):
                related_section = sections[int(si)]
                if (related_section.name, related_section.header["sh_size"]) in discarded:
                    continue
            node_name, node_attrs = symbol_to_node(filename, s)
            graph.add_node(node_name, **node_attrs)
        if si not in symbols_by_section:
            symbols_by_section[si] = []
        symbols_by_section[si].append(s)


    for i, sect in enumerate(sections):
        if sect.name in IGNORE_SECTIONS:
            continue
            
        if (sect.name, sect.header["sh_size"]) in discarded:
            continue
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
            source_section_index = sect.header["sh_info"]
            source_section = sections[source_section_index]
            if source_section.name in IGNORE_SECTIONS:
                continue

            if (source_section.name, source_section.header["sh_size"]) in discarded:
                continue

            # Node name from symbol
            for s in symbols_by_section[source_section_index]:
                if s["st_size"] == 0:
                    continue
                source_symbol_name, symbol_attrs = symbol_to_node(filename, s)
                graph.add_node(source_symbol_name, **symbol_attrs)

            # Node name from section
            if not source_symbol_name:
                source_symbol_name, section_attrs = section_to_node(filename, source_section)
                graph.add_node(source_symbol_name, **section_attrs)

            for r in sect.iter_relocations():
                if r["r_info_sym"] == 0:
                    continue
                s = symbols[r["r_info_sym"]]
                dest_section_index = s["st_shndx"]

                # Undefined symbols must be globals
                if dest_section_index == "SHN_UNDEF":
                    dest_symbol_name, symbol_attrs = symbol_to_node(filename, s)
                    graph.add_node(dest_symbol_name, **symbol_attrs)
                    graph.add_edge(source_symbol_name, dest_symbol_name)
                    continue

                # Ignore self loops
                if dest_section_index == source_section_index:
                    continue

                # Node name from symbol
                dest_symbol_name = None
                for s in symbols_by_section[dest_section_index]:
                    if s["st_size"] == 0:
                        continue
                    dest_symbol_name, symbol_attrs = symbol_to_node(filename, s)
                    graph.add_node(dest_symbol_name, **symbol_attrs)

                # Node name from section
                if not dest_symbol_name:
                    dest_symbol_name, section_attrs = section_to_node(filename, sections[dest_section_index])
                    graph.add_node(dest_symbol_name, **section_attrs)

                # print(source_symbol_name, "->", dest_symbol_name)

                graph.add_edge(source_symbol_name, dest_symbol_name)

def process_map_file(filename, graph):
    path = pathlib.Path(filename)
    top = path.parent.parent
    with open(filename, "r") as f:
        in_archive_include = 0
        in_discarded_sections = 0
        section_name = None
        included = {}
        discarded = {}
        for line in f:
            if line == "Archive member included to satisfy reference by file (symbol)\n":
                in_archive_include = 2
                continue
            if in_archive_include > 0:
                if line == "\n":
                    in_archive_include -= 1
                    continue
                if line[0] != " ":
                    # Skip the reasons why archives are included. We should be able to figure it out.
                    archive, obj = line.strip().split("(")
                    obj = obj.strip(")")
                    archive = pathlib.Path(archive)
                    if not archive.is_absolute():
                        archive = top / archive
                    archive = archive.resolve()
                    if archive not in included:
                        included[archive] = set()
                    included[archive].add(obj.encode("utf-8"))

            if line == "Discarded input sections\n":
                in_discarded_sections = 2
                continue
            if in_discarded_sections > 0:
                if line == "\n":
                    in_discarded_sections -= 1
                    # if in_discarded_sections == 0:
                    #     raise RuntimeError()
                    continue
                split = line.split()
                if len(split) in (1, 4):
                    section_name = split[0]
                    if len(split) == 1:
                        # Other info is on the next line
                        continue
                size = int(split[-2], 0)
                filename = split[-1]

                if ".a(" in filename:
                    archive, obj = filename.split("(")
                    obj = obj.strip(")")
                    archive = pathlib.Path(archive)
                    if not archive.is_absolute():
                        archive = top / archive
                    archive = archive.resolve()
                    if archive not in discarded:
                        discarded[archive] = {}
                    if obj not in discarded[archive]:
                        discarded[archive][obj] = set()
                    discarded[archive][obj].add((section_name, size))
                else:
                    path = pathlib.Path(filename)
                    if not path.is_absolute():
                        path = top / path
                    path = path.resolve()
                    if path not in discarded:
                        discarded[path] = set()
                    discarded[path].add((section_name, size))

            if line.startswith("LOAD"):
                fn = pathlib.Path(line[5:].strip())
                if not fn.is_absolute():
                    fn = top / fn
                fn = fn.resolve()
                if fn.suffix == ".a":
                    with arpy.Archive(fn) as ar:
                        if fn not in included:
                            continue
                        else:
                            print(f"{fn}")
                        for ofn in ar.namelist():
                            if ofn not in included[fn]:
                                continue
                            obj = ofn.decode("utf-8")
                            print(f"\t{obj}")
                            d = discarded.get(fn, {obj:set()}).get(obj, set())
                            with ar.open(ofn) as f2:
                                process_object_file(f2, str(fn) + ":" + obj, graph, d)
                elif fn.suffix == ".o":
                    try:
                        d = discarded.get(fn, set())
                        print(fn)
                        with open(fn, 'rb') as f2:
                            process_object_file(f2, str(fn), graph, d)
                    except BaseException as e:
                        print(e)
                        raise

if __name__ == '__main__':
    graph = nx.DiGraph()
    if sys.argv[1].endswith(".o"):
        for filename in sys.argv[1:]:
            with open(filename, 'rb') as f:
                    process_object_file(f, filename, graph)
    elif sys.argv[1].endswith(".map"):
        process_map_file(sys.argv[1], graph)

    for node in graph.nodes():
        in_degree = graph.in_degree(node)
        if in_degree == 0:
            pass
            # print(node)
        else:
            w = 1 / in_degree
            for _, _, data in graph.in_edges(node, data=True):
                data["weight"] = w

    nx.write_gexf(graph, "test.gexf")

    print(graph.number_of_nodes(), "nodes")
    print(graph.number_of_edges(), "edges")

    # # Add clusters
    # a = nx.nx_agraph.to_agraph(graph)
    # nodes_by_file = {}
    # for node, filename in graph.nodes(data="source_file"):
    #     if not filename:
    #         continue
    #     if filename not in nodes_by_file:
    #         nodes_by_file[filename] = set()
    #     nodes_by_file[filename].add(node)

    # for filename in nodes_by_file:
    #     a.add_subgraph(nodes_by_file[filename], "cluster" + str(filename), label=filename, color="azure", style="filled")
    # a.write("test.dot")
