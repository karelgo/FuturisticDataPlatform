"""CARINA reference implementation — laptop profile.

A single-node embodiment of the CARINA design (see /docs): the data contract
is the hub artifact, DuckDB is the compute lane, quality checks are compiled
from contracts, every platform action lands in a hash-chained evidence log,
and all consumption — human or agent — goes through the semantic layer.
"""

__version__ = "0.1.0"
