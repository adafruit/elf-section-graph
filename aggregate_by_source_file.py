import networkx
import json
import pathlib

graph = networkx.read_gexf("test.gexf")

source_files = {}

ag = networkx.DiGraph()
c = 0
all_subpartitions = []
sizes = graph.nodes.data("size_bytes")
sources = graph.nodes.data("source_file")
for node in graph.nodes():
    sf = sources[node]
    size = sizes[node]
    if sf is None:
        continue
    if sf not in source_files:
        source_files[sf] = 0
    if not size:
        print(node, sf, size)
        continue
    source_files[sf] += size
    for e in graph[node]:
        if not sf or not sources[e]:
            continue
        if sf == sources[e]:
            continue
        ag.add_edge(sf, sources[e])

tree = {}

for s in source_files:
    path = pathlib.Path(s)
    size = source_files[s]
    if size is None :
        continue
    print(path.parts)
    level = tree
    parent = None
    for part in path.parts:
        if part not in level:
            level[part] = {"name": part, "children": {}}
        parent = level[part]
        level = level[part]["children"]
    parent["value"] = size
    ag.add_node(s, size_bytes=size)

def to_child_lists(d):
    print(d)
    if not d:
        return None
    l = []
    for k in d:
        d[k]["children"] = to_child_lists(d[k]["children"])
        l.append(d[k])
    return l

tree = to_child_lists(tree)
root_name = []
parent = None
while len(tree) == 1:
    if parent:
        print(parent["name"])
        root_name.append(parent["name"])
    parent = tree[0]
    tree = tree[0]["children"]

print(root_name)

parent["name"] = "".join(root_name) + "/" + parent["name"]

pathlib.Path("tree.json").write_text(json.dumps(parent))

print(ag.number_of_nodes(), "nodes")
print(ag.number_of_edges(), "edges")

networkx.write_gexf(ag, "sources.gexf")
