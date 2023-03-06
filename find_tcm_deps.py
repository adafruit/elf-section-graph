import networkx
import sys

graph = networkx.read_gexf("test.gexf")

def print_successors(node, remaining_depth=1, current_depth=0):
    print("\t"*current_depth + node, hex(graph.nodes[node].get("address", 0xdeadbeef)))
    if remaining_depth > 0:
        for successor in graph.successors(node):
            print_successors(successor, remaining_depth-1, current_depth+1)


for node in graph.nodes():
    if graph.nodes[node].get("address", 0xdeadbeef) < 32 * 1024:
        print_successors(node, remaining_depth=2)
        print()

