import networkx

graph = networkx.read_gexf("test.gexf")

def expand(node):
    done = set((node,))
    working = set(graph.successors(node))
    inspected = set()
    while working:
        wip = working.pop()
        p = set(graph.predecessors(wip))
        if p <= done:
            done.add(wip)
            working.update(set(graph.successors(wip)) - done, inspected)
            inspected.clear()
        else:
            inspected.add(wip)
    return done

c = 0
all_subpartitions = []
for node in graph.nodes():
    bind = graph.nodes.data("bind")[node]
    if graph.in_degree(node) == 0:
        print(node)
        done = expand(node)
        print(done)
        if len(done) > 1:
            c += 1
            total_size = sum((graph.nodes(data="size_bytes")[z] or 0 for z in done))
            all_subpartitions.append((bind, node, len(done), total_size))

for s in sorted(all_subpartitions, key=lambda x: x[-1]):
    print(*s)

networkx.write_gexf(graph, "roots.gexf")
