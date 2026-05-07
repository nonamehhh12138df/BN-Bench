from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class BayesianNetwork:
    """A lightweight Bayesian network structure object."""

    name: str
    nodes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]
    source_file: str
    format: str = "network"
    paths: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        data = {
            "name": self.name,
            "nodes": list(self.nodes),
            "edges": [list(edge) for edge in self.edges],
            "source_file": self.source_file,
            "format": self.format,
        }
        if self.paths:
            data["paths"] = [list(path) for path in self.paths]
        if self.metadata:
            data["metadata"] = self.metadata
        return data

    def to_networkx(self):
        """Convert to a networkx.DiGraph."""
        try:
            import networkx as nx
        except ImportError as exc:
            raise ImportError(
                "Install the optional dependency with `pip install bnbench[networkx]` "
                "to use to_networkx()."
            ) from exc

        graph = nx.DiGraph()
        graph.add_nodes_from(self.nodes)
        graph.add_edges_from(self.edges)
        return graph

    def edge_dataframe(self):
        """Return edges as a pandas DataFrame with columns `from` and `to`."""
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "Install the optional dependency with `pip install bnbench[pandas]` "
                "to use edge_dataframe()."
            ) from exc

        return pd.DataFrame(self.edges, columns=["from", "to"])


def _network_resource_root():
    return resources.files("bnbench").joinpath("data", "networks")


def _network_key(value: str | Path) -> str:
    stem = Path(str(value)).name
    stem = re.sub(r"\.json$", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"_gt$", "", stem, flags=re.IGNORECASE)
    return re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_").lower()


def _iter_network_files() -> list[Any]:
    root = _network_resource_root()
    return sorted(
        [path for path in root.iterdir() if path.name.lower().endswith(".json")],
        key=lambda path: _network_key(path.name),
    )


def _dedupe_preserve_order(items: Iterable[Any]) -> tuple[Any, ...]:
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return tuple(output)


def _edges_from_paths(paths: Iterable[Iterable[str]]) -> tuple[tuple[str, str], ...]:
    edges: list[tuple[str, str]] = []
    for path in paths:
        sequence = tuple(path)
        for left, right in zip(sequence, sequence[1:]):
            edges.append((left, right))
    return _dedupe_preserve_order(edges)


def _normalise(parsed: Any, fallback_name: str, source_file: str) -> BayesianNetwork:
    if isinstance(parsed, dict) and "nodes" in parsed and "edges" in parsed:
        nodes = tuple(str(node) for node in parsed["nodes"])
        edges = tuple((str(edge[0]), str(edge[1])) for edge in parsed["edges"])
        name = str(parsed.get("name") or fallback_name)
        network = BayesianNetwork(
            name=name,
            nodes=_dedupe_preserve_order(nodes),
            edges=_dedupe_preserve_order(edges),
            source_file=source_file,
            format="network",
            metadata={k: v for k, v in parsed.items() if k not in {"name", "nodes", "edges"}},
        )
    elif isinstance(parsed, list):
        paths = tuple(tuple(str(node) for node in path) for path in parsed)
        edges = _edges_from_paths(paths)
        nodes = _dedupe_preserve_order(node for path in paths for node in path)
        network = BayesianNetwork(
            name=fallback_name,
            nodes=nodes,
            edges=edges,
            source_file=source_file,
            format="paths",
            paths=paths,
        )
    else:
        raise ValueError(
            f"{source_file} has an unsupported format. Expected a network dict "
            "or a list of causal paths."
        )

    validate_network(network)
    return network


def list_networks() -> list[str]:
    """List available network identifiers."""
    return [_network_key(path.name) for path in _iter_network_files()]


def load_network(name: str, *, raw: bool = False) -> BayesianNetwork | Any:
    """Load a bundled Bayesian network.

    Parameters
    ----------
    name:
        Network identifier, such as ``"asia"``, ``"student"``, or
        ``"hip_fracture"``.
    raw:
        If true, return the parsed JSON object without normalization.
    """
    wanted = _network_key(name)
    matches = {network_name: path for network_name, path in zip(list_networks(), _iter_network_files())}

    if wanted not in matches:
        available = ", ".join(matches)
        raise KeyError(f"Unknown network {name!r}. Available networks: {available}")

    path = matches[wanted]
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if raw:
        return parsed
    return _normalise(parsed, wanted, path.name)


def validate_network(network: BayesianNetwork) -> bool:
    """Validate that edges only reference declared nodes."""
    nodes = set(network.nodes)
    unknown = sorted({node for edge in network.edges for node in edge if node not in nodes})
    if unknown:
        raise ValueError(f"Edges reference unknown nodes: {', '.join(unknown)}")
    return True


def network_summary() -> list[dict[str, Any]]:
    """Return one summary row per bundled network."""
    rows = []
    for name in list_networks():
        network = load_network(name)
        rows.append(
            {
                "name": network.name,
                "identifier": name,
                "type": "structure",
                "format": network.format,
                "nodes": len(network.nodes),
                "arcs": len(network.edges),
                "source": network.source_file,
            }
        )
    return rows
