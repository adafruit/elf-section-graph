# elf-section-graph
Construct a graph (aka network) describing the relationship of sections in an elf file

```sh
python elf_symbol_graph.py ../circuitpython/ports/atmel-samd/build-feather_m0_express/firmware.elf.map
```

Individual .o files are loaded based on the .map file.

This outputs to a `test.gxf` file that some of the other scripts analyze.

The expectation now is that you edit the files to your needs.
