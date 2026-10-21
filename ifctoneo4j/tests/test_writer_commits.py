"""
The writer must commit batch by batch: one transaction around the whole graph overflows
Neo4j's transaction memory pool on large models.
"""

from types import SimpleNamespace

from ..neo4j.writer import Neo4jWriter


class _Result:
    def __init__(self, log, cypher):
        self.log, self.cypher = log, cypher

    def consume(self):
        self.log.append(("consumed", self.cypher.split(" ", 1)[0]))


class _Session:
    def __init__(self, log):
        self.log = log

    def run(self, cypher, **params):
        self.log.append(("run", len(params["rows"])))
        return _Result(self.log, cypher)

    def begin_transaction(self):
        raise AssertionError("the writer must not wrap the graph in one transaction")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Driver:
    def __init__(self, log):
        self.log = log

    def session(self, database=None):
        return _Session(self.log)


def _traversal(n_nodes, n_rels):
    nodes = [{"uri": f"u{i}", "labels": ["Element", "Door"], "props": {"name": str(i)}} for i in range(n_nodes)]
    rels = [{"from_uri": f"u{i}", "to_uri": f"u{i + 1}", "rel_type": "CONTAINS_ELEMENT", "props": {}}
            for i in range(n_rels)]
    return SimpleNamespace(nodes=nodes, rels=rels, prop_nodes=[], prop_rels=[])


def test_every_batch_is_its_own_committed_statement():
    log = []
    writer = Neo4jWriter(_Driver(log), batch_size=500)
    counts = writer.write(_traversal(1200, 1199))
    assert counts == {"nodes": 1200, "rels": 1199}
    runs = [n for kind, n in log if kind == "run"]
    assert runs == [500, 500, 200, 500, 500, 199]             # node batches, then relationship batches
    assert [k for k, _ in log].count("consumed") == len(runs)  # each result consumed, so errors surface per batch
