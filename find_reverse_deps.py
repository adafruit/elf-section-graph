import networkx
import sys

graph = networkx.read_gexf("test.gexf")

def print_predecessors(node, remaining_depth=1, current_depth=0):
    print("\t"*current_depth + node)
    if remaining_depth > 0:
        for predecessor in graph.predecessors(node):
            print_predecessors(predecessor, remaining_depth-1, current_depth+1)


for node in graph.nodes():
    for target_symbol in sys.argv[1:]:
        if target_symbol in node:
            print_predecessors(node, remaining_depth=2)
            print()

