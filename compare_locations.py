import json
import networkx
import sys
from operator import itemgetter

graph = networkx.read_gexf("test.gexf")
offset = 0x60000400

with open(sys.argv[-1], "rb") as f:
    bin_file = memoryview(f.read())

with open("bookmarks.hexbm", "r") as f:
    located = json.load(f)

located["bookmarks"].sort(key=lambda x: x["region"]["address"])
for bookmark in located["bookmarks"]:
    comment = bookmark["comment"]
    if not comment:
        comment = bookmark["name"]
    node_info = graph.nodes()[comment]
    fast_address = bookmark["region"]["address"]
    address_now = node_info["address"]
    address_diff = address_now - fast_address
    unoffset = fast_address - offset
    print(hex(bookmark["region"]["address"]), hex(address_now), hex(address_diff), hex(unoffset), comment)

