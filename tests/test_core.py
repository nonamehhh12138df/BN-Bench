from bnbench import list_networks, load_network, network_summary


def test_list_networks_includes_expected_datasets():
    names = list_networks()
    assert "asia" in names
    assert "hip_fracture" in names
    assert "student" in names


def test_load_network_chain_format():
    asia = load_network("asia")
    assert asia.name == "asia"
    assert asia.format == "paths"
    assert len(asia.nodes) == 8
    assert ("Asia", "Tuberculosis") in asia.edges
    assert asia.paths


def test_load_network_path_format():
    hip = load_network("hip_fracture")
    assert hip.format == "paths"
    assert ("Age", "BMD") in hip.edges
    assert hip.paths


def test_network_summary_matches_listed_networks():
    assert len(network_summary()) == len(list_networks())
