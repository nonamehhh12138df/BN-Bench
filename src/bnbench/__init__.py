"""Python accessors for the BN-Bench Bayesian network repository."""

from .core import (
    BayesianNetwork,
    list_networks,
    load_network,
    network_summary,
    validate_network,
)

__all__ = [
    "BayesianNetwork",
    "list_networks",
    "load_network",
    "network_summary",
    "validate_network",
]

__version__ = "0.1.0"
