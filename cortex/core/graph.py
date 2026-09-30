"""FalkorDB connection and graph names."""
import os
from functools import lru_cache

from falkordb import FalkorDB

KG = "cortex_kg"      # knowledge graph built from the PDFs
OPS = "cortex_ops"    # operational graph (customers, accounts, transactions)
SANDBOX_PREFIX = "sandbox_"  # one isolated graph per upload session


@lru_cache(maxsize=1)
def db():
    return FalkorDB(host=os.getenv("FALKOR_HOST", "localhost"), port=int(os.getenv("FALKOR_PORT", "6379")))


def graph(name=KG):
    return db().select_graph(name)
