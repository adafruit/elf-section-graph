import json
import networkx
import sys
from operator import itemgetter

import concurrent.futures

graph = networkx.read_gexf("test.gexf")

with open(sys.argv[1], "rb") as f:
    bin_file = memoryview(f.read())
offset = 0x60000400

remapped = []

def locate(node):
    if len(sys.argv) > 2:
        found = False
        for substring in sys.argv[2:]:
            if substring in node:
                found = True
                break

        if not found:
            return
    out_degree = graph.nodes(node)
    node_info = graph.nodes[node]
    contents = graph.nodes[node].get("postlink", "")

    if not contents:
        return

    print(node)

    contents = bytes.fromhex(contents)
    stripped = contents.strip(b"\x00")
    if contents in bin_file:
        count = bin_file.count(contents)
        if count > 1:
            # print(f"{count} copies of {node}")
            # print(contents.hex(" ", 4))
            return
        found_address = offset + bin_file.index(contents)
        return (found_address, node, graph.nodes[node]["size_bytes"], len(contents))
    elif node_info["bind"] == "weak":
        pass
    elif stripped and stripped in bin_file:
        # print("found stripped", node, stripped)
        pass
    # elif out_degree == 0:
    #     print()
    #     print(node, contents.strip(b"\x00"))
    elif len(contents) >= 8:
        # fuzzy search
        best_match_count = 0
        best_match_start = 0
        for i in range(len(bin_file)):
            matched = sum(1 if a == b else 0 for a, b in zip(contents, bin_file[i:]))
            if matched > best_match_count:
                best_match_start = i
                best_match_count = matched
        return (offset + best_match_start, node, graph.nodes[node]["size_bytes"], len(contents))
    else:
        # print(node, "too short")
        pass


def main():
    print(sys.argv[2:])
    with concurrent.futures.ProcessPoolExecutor(max_workers=24*2) as executor:
        remapped = list(executor.map(locate, graph.nodes(), chunksize=1000))
    remapped = [x for x in remapped if x is not None]
    remapped.sort(key=itemgetter(0))

    bookmarks = []
    matched_size = 0
    for address, node, size, content_size in remapped:
        # print(hex(address), node, size, content_size)
        matched_size += content_size
        name = node
        comment = ""
        if ":" in name:
            name = name.split(":")[-1]
            comment = node
        bookmarks.append({"color": 1341756994, "comment": comment, "locked": False, "name": name, "region": {"address":address, "size": content_size}})

    print(f"matched {matched_size} bytes of {len(bin_file)}")
    with open("bookmarks.hexbm", "w") as f:
        json.dump({"bookmarks": bookmarks}, f, indent=1)

if __name__ == '__main__':
    main()
