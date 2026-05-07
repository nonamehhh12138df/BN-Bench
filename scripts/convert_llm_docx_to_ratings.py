"""Convert LLM survey response tables from a DOCX file into ratings CSVs.

The source document is expected to contain network sections named like
``2.1 The Fauna Distribution Network``. Each section should have two response
tables:

1. ordering-based causal ratings on [-10, 10]
2. edge-based direct influence labels on [-1, 0, 1]

Each output folder contains ``ordering_based_ratings.csv``,
``edge_based_ratings.csv``, and ``metadata.json``.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


DEFAULT_MODEL = "ChatGPT 4.0"
DEFAULT_EXPERT_TYPE = "llm_simulated_expert"
DEFAULT_RUN_ID = "run_001"
DEFAULT_PROMPT_ID = "docx_llm_survey_v1"
ORDERING_RATINGS_FILE = "ordering_based_ratings.csv"
EDGE_RATINGS_FILE = "edge_based_ratings.csv"


@dataclass
class SectionTables:
    section_id: str
    section_title: str
    network: str
    slug: str
    rating_table_index: int | None = None
    direction_table_index: int | None = None
    rating_rows: list[dict[str, str]] | None = None
    direction_rows: list[dict[str, str]] | None = None


def iter_blocks(document: Document) -> Iterable[Paragraph | Table]:
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield Table(child, document)


def slugify(text: str) -> str:
    text = re.sub(r"\bnetwork\b", "", text, flags=re.IGNORECASE)
    text = text.replace("The ", "")
    text = text.replace("’", "")
    text = text.replace("'", "")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    return slug or "network"


def clean_network_title(title: str) -> str:
    title = re.sub(r"^\s*The\s+", "", title)
    title = re.sub(r"\s+Network\s*$", "", title, flags=re.IGNORECASE)
    return title.strip()


def dedupe_slug(slug: str, seen: dict[str, int]) -> str:
    seen[slug] = seen.get(slug, 0) + 1
    if seen[slug] == 1:
        return slug
    return f"{slug}_{seen[slug]}"


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


def parse_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    match = re.search(r"-?\d+", value)
    if not match:
        return None
    return int(match.group(0))


def table_kind(table: Table) -> str | None:
    if not table.rows:
        return None
    header = " ".join(cell.text for cell in table.rows[0].cells)
    header = re.sub(r"\s+", " ", header)
    if "[-10, 10]" in header:
        return "rating"
    if "[-1, 0, 1]" in header or "[-1, 0,  1]" in header:
        return "direction"
    return None


def extract_response_rows(table: Table, value_column: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for row in table.rows[1:]:
        cells = [cell.text.strip() for cell in row.cells]
        for pair_index, rating_index in ((0, 1), (2, 3)):
            if pair_index >= len(cells) or rating_index >= len(cells):
                continue
            pair_text = normalize_pair_text(cells[pair_index])
            value_text = cells[rating_index].strip()
            if not pair_text:
                continue
            source, target = split_pair(pair_text)
            value = parse_int(value_text)
            rows.append(
                {
                    "pair_text": pair_text,
                    "source": source,
                    "target": target,
                    value_column: "" if value is None else str(value),
                }
            )

    return rows


def collect_sections(docx_path: Path) -> list[SectionTables]:
    document = Document(docx_path)
    sections: list[SectionTables] = []
    current: SectionTables | None = None
    seen_slugs: dict[str, int] = {}
    table_index = 0

    for block in iter_blocks(document):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            match = re.match(r"^(2\.\d+)\s+(.+)$", text)
            if match and not re.match(r"^2\.\d+\.\d+", text):
                section_id = match.group(1)
                section_title = match.group(2).strip()
                network = clean_network_title(section_title)
                slug = dedupe_slug(slugify(network), seen_slugs)
                current = SectionTables(
                    section_id=section_id,
                    section_title=section_title,
                    network=network,
                    slug=slug,
                    rating_rows=[],
                    direction_rows=[],
                )
                sections.append(current)
            continue

        table_index += 1
        if current is None:
            continue
        kind = table_kind(block)
        if kind == "rating" and current.rating_table_index is None:
            current.rating_table_index = table_index
            current.rating_rows = extract_response_rows(block, "raw_score")
        elif kind == "direction" and current.direction_table_index is None:
            current.direction_table_index = table_index
            current.direction_rows = extract_response_rows(block, "direction_label")

    return sections


def base_output_row(section: SectionTables, row: dict[str, str], idx: int) -> dict[str, str]:
    return {
        "network": section.slug,
        "network_label": section.network,
        "section_id": section.section_id,
        "model": DEFAULT_MODEL,
        "expert_type": DEFAULT_EXPERT_TYPE,
        "run_id": DEFAULT_RUN_ID,
        "pair_id": f"{section.slug}_pair_{idx:03d}",
        "source": row["source"],
        "target": row["target"],
        "prompt_id": DEFAULT_PROMPT_ID,
    }


def ordering_rows(section: SectionTables) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []

    for idx, row in enumerate(section.rating_rows or [], start=1):
        output_row = base_output_row(section, row, idx)
        output_row["protocol"] = "ordering_based"
        output_row["raw_score"] = row["raw_score"]
        output.append(output_row)

    return output


def edge_rows(section: SectionTables) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []

    for idx, row in enumerate(section.direction_rows or [], start=1):
        output_row = base_output_row(section, row, idx)
        output_row["protocol"] = "edge_based"
        output_row["direction_label"] = row["direction_label"]
        output.append(output_row)

    return output


def write_outputs(sections: list[SectionTables], output_root: Path, source_docx: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    ordering_fieldnames = [
        "network",
        "network_label",
        "section_id",
        "model",
        "expert_type",
        "run_id",
        "pair_id",
        "source",
        "target",
        "prompt_id",
        "protocol",
        "raw_score",
    ]
    edge_fieldnames = [
        "network",
        "network_label",
        "section_id",
        "model",
        "expert_type",
        "run_id",
        "pair_id",
        "source",
        "target",
        "prompt_id",
        "protocol",
        "direction_label",
    ]

    for section in sections:
        if not section.rating_rows:
            continue

        ordering = ordering_rows(section)
        edge = edge_rows(section)
        section_dir = output_root / section.slug
        section_dir.mkdir(parents=True, exist_ok=True)

        stale_combined = section_dir / "ratings.csv"
        if stale_combined.exists():
            stale_combined.unlink()

        with (section_dir / ORDERING_RATINGS_FILE).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=ordering_fieldnames)
            writer.writeheader()
            writer.writerows(ordering)

        with (section_dir / EDGE_RATINGS_FILE).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=edge_fieldnames)
            writer.writeheader()
            writer.writerows(edge)

        metadata = {
            "network": section.slug,
            "network_label": section.network,
            "section_id": section.section_id,
            "section_title": section.section_title,
            "model": DEFAULT_MODEL,
            "expert_type": DEFAULT_EXPERT_TYPE,
            "run_id": DEFAULT_RUN_ID,
            "prompt_id": DEFAULT_PROMPT_ID,
            "rating_files": {
                "ordering_based": ORDERING_RATINGS_FILE,
                "edge_based": EDGE_RATINGS_FILE,
            },
            "rating_scales": {
                "ordering_based": {
                    "column": "raw_score",
                    "description": "integer causal rating in [-10, 10]",
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
            "source_tables": {
                "causal_rating_table_index": section.rating_table_index,
                "direct_influence_table_index": section.direction_table_index,
            },
            "num_pairs": {
                "ordering_based": len(ordering),
                "edge_based": len(edge),
            },
        }

        with (section_dir / "metadata.json").open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, ensure_ascii=False)
            handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("docx", type=Path)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("ratings") / "llm",
        help="Root directory where per-network rating folders are written.",
    )
    args = parser.parse_args()

    sections = collect_sections(args.docx)
    write_outputs(sections, args.output_root, args.docx)
    total_ordering = sum(len(section.rating_rows or []) for section in sections)
    total_edge = sum(len(section.direction_rows or []) for section in sections)
    print(
        "Converted "
        f"{len(sections)} network sections, "
        f"{total_ordering} ordering-based ratings, and "
        f"{total_edge} edge-based ratings."
    )


if __name__ == "__main__":
    main()
