"""Convert human rating spreadsheets into standardized long-form CSV files."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


ORDERING_RATINGS_FILE = "ordering_based_ratings.csv"
EDGE_RATINGS_FILE = "edge_based_ratings.csv"
DEFAULT_PROMPT_ID = "human_survey_v1"


FILENAME_SLUGS = {
    "Human Rating of Causal Influence (E-commerce Network) (Responses).xlsx": ("e_commerce", "E-commerce"),
    "Human Rating of Causal Influence (Supply Chain Network) (Responses).xlsx": ("supply_chain", "Supply Chain"),
    "Human Rating of Causal Influence(Aquatic Health Network) (Responses).xlsx": ("aquatic_health", "Aquatic Health"),
    "Human Rating of Causal Influence(Hip Fracture Network) (Responses).xlsx": ("hip_fracture", "Hip Fracture"),
    "Human Rating of Causal Influence(Waterborne Disease Network) (Responses).xlsx": (
        "waterborne_disease",
        "Waterborne Disease",
    ),
    "Student_network_new.xlsx": ("student", "Student"),
}


def normalize_pair_text(text: str) -> str:
    text = text.replace("\u2013", " - ").replace("\u2014", " - ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_pair(pair: str) -> tuple[str, str]:
    normalized = normalize_pair_text(pair)
    parts = re.split(r"\s+-\s+", normalized, maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"Could not split pair text: {pair!r}")
    return parts[0].strip(), parts[1].strip()


def slugify(text: str) -> str:
    text = re.sub(r"\bnetwork\b", "", text, flags=re.IGNORECASE)
    text = text.replace("’", "").replace("'", "")
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()


def parse_rating(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def participant_column(columns: list[str]) -> str:
    for column in columns:
        normalized = column.lower().strip()
        if "id" in normalized and ("input" in normalized or normalized.endswith(" id")):
            return column
    raise ValueError("Could not identify participant ID column.")


def pair_columns(columns: list[str], participant_col: str) -> list[str]:
    skipped = {participant_col, "Timestamp"}
    output = []
    for column in columns:
        if column in skipped:
            continue
        if str(column).startswith("Unnamed:"):
            continue
        if " - " in normalize_pair_text(str(column)):
            output.append(column)
    return output


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def convert_wide_xlsx(path: Path, output_root: Path) -> dict[str, Any]:
    slug, label = FILENAME_SLUGS.get(path.name, (slugify(path.stem), path.stem))
    df = pd.read_excel(path)
    df.columns = [str(column).strip() for column in df.columns]
    participant_col = participant_column(list(df.columns))
    pair_cols = pair_columns(list(df.columns), participant_col)
    rows: list[dict[str, str]] = []

    for response_idx, record in df.iterrows():
        response_id = f"{slug}_participant_{response_idx + 1:03d}"
        for pair_idx, pair_col in enumerate(pair_cols, start=1):
            source, target = split_pair(str(pair_col))
            rows.append(
                {
                    "network": slug,
                    "network_label": label,
                    "participant_id": response_id,
                    "response_id": response_id,
                    "pair_id": f"{slug}_pair_{pair_idx:03d}",
                    "source": source,
                    "target": target,
                    "prompt_id": DEFAULT_PROMPT_ID,
                    "protocol": "ordering_based",
                    "raw_score": parse_rating(record[pair_col]),
                }
            )

    section_dir = output_root / slug
    section_dir.mkdir(parents=True, exist_ok=True)
    ordering_fields = [
        "network",
        "network_label",
        "participant_id",
        "response_id",
        "pair_id",
        "source",
        "target",
        "prompt_id",
        "protocol",
        "raw_score",
    ]
    write_rows(section_dir / ORDERING_RATINGS_FILE, ordering_fields, rows)

    metadata = {
        "network": slug,
        "network_label": label,
        "rating_files": {"ordering_based": ORDERING_RATINGS_FILE},
        "rating_scales": {
            "ordering_based": {
                "column": "raw_score",
                "description": "human ordering-based causal rating, typically in [-10, 10]",
            }
        },
        "num_participants": int(df.shape[0]),
        "num_pairs": {"ordering_based": len(pair_cols)},
        "num_ratings": {"ordering_based": len(rows)},
    }
    return metadata


def convert_asia_ordering(path: Path, output_root: Path) -> dict[str, Any]:
    df = pd.read_csv(path)
    rows: list[dict[str, str]] = []
    pair_lookup: dict[tuple[str, str], str] = {}

    for _, record in df.iterrows():
        source = str(record["factor_a"]).strip()
        target = str(record["factor_b"]).strip()
        key = (source, target)
        if key not in pair_lookup:
            pair_lookup[key] = f"asia_pair_{len(pair_lookup) + 1:03d}"
        rows.append(
            {
                "network": "asia",
                "network_label": "Asia",
                "participant_id": f"asia_participant_{int(record['response_id']) + 1:03d}",
                "response_id": f"asia_participant_{int(record['response_id']) + 1:03d}",
                "pair_id": pair_lookup[key],
                "source": source,
                "target": target,
                "prompt_id": DEFAULT_PROMPT_ID,
                "protocol": "ordering_based",
                "raw_score": parse_rating(record["rating"]),
            }
        )

    fields = [
        "network",
        "network_label",
        "participant_id",
        "response_id",
        "pair_id",
        "source",
        "target",
        "prompt_id",
        "protocol",
        "raw_score",
    ]
    asia_dir = output_root / "asia"
    asia_dir.mkdir(parents=True, exist_ok=True)
    write_rows(asia_dir / ORDERING_RATINGS_FILE, fields, rows)

    return {
        "num_participants": int(df["response_id"].nunique()),
        "num_pairs": len(pair_lookup),
        "num_ratings": len(rows),
    }


def convert_asia_edge(path: Path, output_root: Path) -> dict[str, Any]:
    df = pd.read_csv(path)
    df.columns = [str(column).strip() for column in df.columns]
    participant_col = participant_column(list(df.columns))
    pair_cols = pair_columns(list(df.columns), participant_col)
    rows: list[dict[str, str]] = []

    for response_idx, record in df.iterrows():
        response_id = f"asia_participant_{response_idx + 1:03d}"
        for pair_idx, pair_col in enumerate(pair_cols, start=1):
            source, target = split_pair(str(pair_col))
            rows.append(
                {
                    "network": "asia",
                    "network_label": "Asia",
                    "participant_id": response_id,
                    "response_id": response_id,
                    "pair_id": f"asia_pair_{pair_idx:03d}",
                    "source": source,
                    "target": target,
                    "prompt_id": DEFAULT_PROMPT_ID,
                    "protocol": "edge_based",
                    "direction_label": parse_rating(record[pair_col]),
                }
            )

    fields = [
        "network",
        "network_label",
        "participant_id",
        "response_id",
        "pair_id",
        "source",
        "target",
        "prompt_id",
        "protocol",
        "direction_label",
    ]
    asia_dir = output_root / "asia"
    asia_dir.mkdir(parents=True, exist_ok=True)
    write_rows(asia_dir / EDGE_RATINGS_FILE, fields, rows)

    return {
        "num_participants": int(df.shape[0]),
        "num_pairs": len(pair_cols),
        "num_ratings": len(rows),
    }


def write_metadata(path: Path, metadata: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("ratings") / "human",
        help="Directory containing human rating spreadsheets.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("ratings") / "human",
        help="Root directory where per-network CSV folders are written.",
    )
    args = parser.parse_args()

    converted = []
    for path in sorted(args.input_root.glob("*.xlsx")):
        metadata = convert_wide_xlsx(path, args.output_root)
        write_metadata(args.output_root / metadata["network"] / "metadata.json", metadata)
        converted.append(metadata)

    asia_dir = args.input_root / "asia"
    asia_ordering_path = asia_dir / "asian_network_human.csv"
    asia_edge_path = asia_dir / "Asian_edge_based.csv"
    if asia_ordering_path.exists() and asia_edge_path.exists():
        ordering = convert_asia_ordering(asia_ordering_path, args.output_root)
        edge = convert_asia_edge(asia_edge_path, args.output_root)
        asia_metadata = {
            "network": "asia",
            "network_label": "Asia",
            "rating_files": {
                "ordering_based": ORDERING_RATINGS_FILE,
                "edge_based": EDGE_RATINGS_FILE,
            },
            "rating_scales": {
                "ordering_based": {
                    "column": "raw_score",
                    "description": "human ordering-based causal rating",
                },
                "edge_based": {
                    "column": "direction_label",
                    "labels": {
                        "1": "source -> target",
                        "-1": "target -> source",
                        "0": "no direct causal influence or uncertain",
                    },
                },
            },
            "num_participants": {
                "ordering_based": ordering["num_participants"],
                "edge_based": edge["num_participants"],
            },
            "num_pairs": {
                "ordering_based": ordering["num_pairs"],
                "edge_based": edge["num_pairs"],
            },
            "num_ratings": {
                "ordering_based": ordering["num_ratings"],
                "edge_based": edge["num_ratings"],
            },
        }
        write_metadata(args.output_root / "asia" / "metadata.json", asia_metadata)
        converted.append(asia_metadata)

    total_datasets = len(converted)
    print(f"Converted {total_datasets} human rating datasets.")


if __name__ == "__main__":
    main()
