# BN-Bench: Human and LLM Causal Knowledge Benchmark

BN-Bench is a curated benchmark library for studying **causal graph learning from human and LLM-generated causal knowledge**.

Unlike standard Bayesian network repositories that mainly provide ground-truth DAGs and synthetic observational data, BN-Bench focuses on **chain-level causal knowledge**. Each network is represented as a collection of directed causal chains. Each chain encodes an ordered causal path, and the union of all chains defines the corresponding ground-truth DAG.

The repository is designed to support experiments on:

- human causal judgment elicitation;
- LLM-simulated expert causal ratings;
- chain-based causal graph recovery;
- crowd aggregation from multiple experts;
- robustness evaluation under noisy or heterogeneous causal beliefs.

---

## Repository Structure

```text
BN-Bench/
├── networks/
│   ├── asia.json
│   ├── road_safety_gt.json
│   ├── hip_fracture_gt.json
│   ├── insurance_gt.json
│   ├── covid_gt.json
│   ├── alzheimer_gt.json
│   └── ...
│
├── ratings/
│   ├── human/
│   │   ├── asia/
│   │   │   ├── edge_based_ratings.csv
│   │   │   ├── ordering_based_ratings.csv
│   │   │   └── metadata.json
│   │   └── ...
│   │
│   └── llm/
│       ├── asia/
│       │   ├── edge_based_ratings.csv
│       │   ├── ordering_based_ratings.csv
│       │   └── metadata.json
│       └── ...
│
├── prompts/
│   ├── human_survey/
│   │   ├── edge_based_prompt.md
│   │   ├── ordering_based_prompt.md
│   │   └── metadata.json
│   │
│   └── llm_experts/
│       ├── single_step_prompt.md
│       ├── multi_step_prompt.md
│       └── metadata.json
│
├── scripts/
│   ├── convert_human_xlsx_to_csv.py
│   └── convert_llm_docx_to_ratings.py
│
├── examples/
│   ├── load_chain_dag.ipynb
│   ├── load_human_ratings.ipynb
│   └── load_llm_ratings.ipynb
│
└── README.md
```

---

## Data Modules

BN-Bench contains three main types of data.

### 1. Chain-Level Ground-Truth DAGs

The `networks/` folder stores the ground-truth causal structures.

Each JSON file contains a list of directed causal chains. For example:

```json
[
  ["Ease of Navigation", "Quality of Web Design", "Customer Satisfaction"],
  ["Web Look and Feel", "Quality of Web Design", "Customer Satisfaction"],
  ["Online Help Information", "Quality of Web Design", "Customer Satisfaction"],
  ["Ease of Checkout", "Quality of Web Design", "Customer Satisfaction"],
  ["Accuracy of Shipment", "Efficiency of Product Delivery", "Customer Satisfaction"],
  ["Accuracy of Shipment", "Timeliness of Delivery", "Customer Satisfaction"],
  ["Accuracy of Shipment", "Quality of Packaging", "Customer Satisfaction"]
]
```

Each inner list represents one directed chain. For example,

```json
["Ease of Navigation", "Quality of Web Design", "Customer Satisfaction"]
```

corresponds to the directed path:

```text
Ease of Navigation -> Quality of Web Design -> Customer Satisfaction
```

The full DAG is obtained by taking the union of all directed edges implied by all chains.

For the example above, the implied directed edges include:

```text
Ease of Navigation -> Quality of Web Design
Quality of Web Design -> Customer Satisfaction
Web Look and Feel -> Quality of Web Design
Online Help Information -> Quality of Web Design
Ease of Checkout -> Quality of Web Design
Accuracy of Shipment -> Efficiency of Product Delivery
Efficiency of Product Delivery -> Customer Satisfaction
Accuracy of Shipment -> Timeliness of Delivery
Timeliness of Delivery -> Customer Satisfaction
Accuracy of Shipment -> Quality of Packaging
Quality of Packaging -> Customer Satisfaction
```

This representation is useful because many human and LLM judgments are naturally expressed as local causal chains rather than as a fully specified adjacency matrix.

### 2. Human Causal Ratings

The `ratings/human/` folder contains causal judgments collected from human participants.

Each dataset is stored as one or two rating files plus metadata. Human datasets include `ordering_based_ratings.csv`; `edge_based_ratings.csv` is included when edge-based labels are available.

```text
ratings/human/{network_name}/ordering_based_ratings.csv
ratings/human/{network_name}/edge_based_ratings.csv
ratings/human/{network_name}/metadata.json
```

In the current release, Asia includes both ordering-based and edge-based human ratings. The other human rating datasets currently include ordering-based ratings only.

The recommended format is:

| Column | Description |
|:--|:--|
| `network` | Name of the reference network |
| `participant_id` | Anonymized participant identifier |
| `pair_id` | Unique ID for the queried variable pair |
| `source` | First variable in the queried pair |
| `target` | Second variable in the queried pair |
| `raw_score` | Ordering-based response score, e.g., an integer in `[-10, 10]` |
| `direction_label` | Edge-based causal direction label |
| `protocol` | Elicitation protocol, such as `edge_based` or `ordering_based` |

The processed direction label follows:

```text
 1 = source -> target
-1 = target -> source
 0 = no perceived causal relation or uncertain
```

Human ratings are used to evaluate how well causal discovery methods can recover chain-level or graph-level structures from noisy, heterogeneous human knowledge.

### 3. LLM Expert Ratings

The `ratings/llm/` folder contains causal ratings generated by LLM-based simulated experts.

Each LLM rating dataset is stored as:

```text
ratings/llm/{network_name}/edge_based_ratings.csv
ratings/llm/{network_name}/ordering_based_ratings.csv
ratings/llm/{network_name}/metadata.json
```

The recommended format for `ordering_based_ratings.csv` is:

| Column | Description |
|:--|:--|
| `network` | Name of the reference network |
| `model` | LLM model name |
| `expert_type` | Simulated expert profile or reasoning style |
| `run_id` | Repeated run identifier |
| `pair_id` | Unique ID for the queried variable pair |
| `source` | First variable in the queried pair |
| `target` | Second variable in the queried pair |
| `raw_score` | Signed ordering-based causal judgment score in `[-10, 10]` |
| `protocol` | Always `ordering_based` |
| `prompt_id` | ID of the prompt template used for elicitation |

The recommended format for `edge_based_ratings.csv` is:

| Column | Description |
|:--|:--|
| `network` | Name of the reference network |
| `model` | LLM model name |
| `expert_type` | Simulated expert profile or reasoning style |
| `run_id` | Repeated run identifier |
| `pair_id` | Unique ID for the queried variable pair |
| `source` | First variable in the queried pair |
| `target` | Second variable in the queried pair |
| `direction_label` | Edge-based direct influence label in `{-1, 0, 1}` |
| `protocol` | Always `edge_based` |
| `prompt_id` | ID of the prompt template used for elicitation |

LLM ratings allow controlled comparisons between different simulated experts, prompt designs, and aggregation strategies.

---

## Included Networks

The current `networks/` folder contains chain-level ground-truth DAGs for multiple domains.

| Network | File | Description |
|:--|:--|:--|
| Asia | `asia.json` | Medical diagnosis network involving respiratory disease variables |
| Student | `Student.json` | Student performance and academic outcome network |
| Insurance | `insurance_gt.json` | Insurance risk assessment network |
| Road Safety | `road_safety_gt.json` | Traffic and road safety causal network |
| Hip Fracture | `hip_fracture_gt.json` | Clinical network for geriatric hip fracture outcomes |
| Covid | `covid_gt.json` | Expert-elicited COVID disease process network |
| Alzheimer | `alzheimer_gt.json` | Medical network related to Alzheimer's disease |
| E-commerce | `E_commerce_gt.json` | Customer experience and online shopping satisfaction network |
| Sachs | `SACHS_gt.json` | Biological signaling network |
| Aquatic | `aquatic_gt.json` | Environmental or aquatic system causal network |
| Flooding Risk | `flooding_risk_gt.json` | Flooding risk assessment network |
| Neuropathic | `neuropathic_gt.json` | Clinical network related to neuropathic conditions |
| Waterborne | `waterborne_gt.json` | Waterborne disease or contamination causal network |

---

## Python Package Setup

Install locally while developing:

```bash
pip install -e .
```

Install from an anonymous GitHub repository:

```bash
pip install git+https://github.com/anonymous-bnbench/bnbench.git
```

After publishing to PyPI, users will be able to install the stable version with:

```bash
pip install bnbench
```

---

## Example: Loading a Chain-Level DAG

```python
import json
from pathlib import Path

def load_chain_dag(path):
    with open(path, "r") as f:
        chains = json.load(f)

    edges = set()
    nodes = set()

    for chain in chains:
        for node in chain:
            nodes.add(node)
        for u, v in zip(chain[:-1], chain[1:]):
            edges.add((u, v))

    return {
        "chains": chains,
        "nodes": sorted(nodes),
        "edges": sorted(edges),
    }

dag = load_chain_dag("networks/E_commerce_gt.json")

print("Nodes:")
print(dag["nodes"])

print("Edges:")
print(dag["edges"])
```

The same networks can also be loaded through the Python package:

```python
from bnbench import list_networks, load_network, network_summary

print(list_networks())
print(network_summary())

dag = load_network("e_commerce")
print(dag.nodes)
print(dag.edges)
print(dag.paths)
```

Optional conversion to NetworkX:

```bash
pip install "bnbench[networkx]"
```

```python
graph = load_network("e_commerce").to_networkx()
```

---

## Benchmark Tasks

BN-Bench supports several benchmark tasks.

### Single-Expert Causal Recovery

Given one expert's pairwise causal ratings, recover the underlying chain-level DAG.

### Crowd Aggregation

Given ratings from multiple human or LLM experts, aggregate their judgments into a single causal structure.

Supported aggregation settings include:

- majority vote;
- score-sum aggregation;
- confidence-weighted aggregation;
- expert-type-aware aggregation;
- recruitment-order experiments, where performance is evaluated as the number of experts increases.

### LLM Expert Evaluation

Compare different LLM-generated expert ratings under controlled prompts and expert profiles.

### Noise Robustness

Evaluate how causal graph recovery methods behave under increasing noise or disagreement in causal judgments.

---

## Evaluation Metrics

BN-Bench supports both ordering-level and graph-level metrics.

| Metric | Purpose |
|:--|:--|
| `D_top` | Measures discrepancy between recovered and ground-truth topological orderings |
| Kendall's Tau | Measures ranking agreement |
| SHD | Structural Hamming Distance between predicted and true graphs |
| Recall | Fraction of true edges recovered |
| Precision | Fraction of predicted edges that are correct |
| FPR | False positive rate |
| F1 | Harmonic mean of precision and recall |
| SID | Optional intervention-oriented structural distance |

For chain-level recovery, metrics can be computed either on the implied DAG or directly on recovered causal chains.

---

## Prompt Templates

Prompt templates used for eliciting causal judgments are stored in `prompts/`.

Human survey prompts are stored in:

```text
prompts/human_survey/
```

LLM expert prompts are stored in:

```text
prompts/llm_experts/
```

These prompts document how pairwise causal questions were presented to human participants or LLM-based simulated experts.

---

## Ethics and Privacy

Human-elicited datasets are anonymized before release. No personally identifiable information is included. Participant IDs are replaced with anonymous identifiers, and only task responses and minimal metadata required for benchmarking are retained.

The released data are intended for research on causal discovery, expert elicitation, and human/LLM causal knowledge aggregation.

---

## Citation

If you use BN-Bench in your research, please cite the corresponding paper:

```bibtex
@misc{bnbench2026,
  title = {BN-Bench: A Benchmark for Learning Causal Graphs from Human and LLM Causal Knowledge},
  author = {Anonymous Authors},
  year = {2026},
  note = {Manuscript under review}
}
```

---

## License

Please check the license file before using or redistributing the data.

---

## Filename Convention

The current release preserves the original file names. For future releases, file names may be standardized to one of the following conventions:

```text
asia_chains.json
student_chains.json
insurance_chains.json
road_safety_chains.json
hip_fracture_chains.json
```

or:

```text
asia_gt.json
student_gt.json
insurance_gt.json
road_safety_gt.json
hip_fracture_gt.json
```
