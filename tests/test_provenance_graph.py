"""Unified provenance mermaid renderer (Increment 6).

One `_mermaid_graph` renders every job: sources (datasets and/or included sub-job
references) → pipeline steps → sink, with canonical collision-safe node ids. These
pin the id-dedup + fan-in wiring and the two structural edge cases (zero steps;
no sources) so the .prov.md rendering - otherwise untested - can't silently drift.
"""

from __future__ import annotations

import re

from provenance import _mermaid_graph


def _ids_and_edges(md: str) -> tuple[set[str], list[tuple[str, str]]]:
    ids: set[str] = set()
    edges: list[tuple[str, str]] = []
    for line in md.splitlines():
        line = line.strip()
        if "-->" in line:
            left, right = (s.strip() for s in line.split("-->"))
            src = left.split("[")[0].strip()
            dst = right.split("[")[0].strip()
            edges.append((src, dst))
            ids.update({src, dst})
        else:
            m = re.match(r"^([0-9A-Za-z_]+)\[", line)
            if m:
                ids.add(m.group(1))
    return ids, edges


def test_collisions_dedupe_and_edges_use_deduped_ids() -> None:
    record = {
        "dataset_paths": ["a/data.pkl", "b/data.pkl"],  # same filename, 2 dirs
        "dataset_hashes": ["sha256:1111", "sha256:2222"],
        "pipeline_steps": ["filter(x=1)", "filter(x=2)"],  # same fnname twice
        "git_commit": "abc123",
        "includes": [],
    }
    md = _mermaid_graph(record, "sink_node")
    ids, edges = _ids_and_edges(md)
    # every declared id is unique (dedup worked)
    id_lines = [ln for ln in md.splitlines() if re.match(r"^\s*[0-9A-Za-z_]+\[", ln)]
    declared = [re.match(r"^\s*([0-9A-Za-z_]+)\[", ln).group(1) for ln in id_lines]
    assert len(declared) == len(set(declared)), declared
    # both same-named datasets present as distinct nodes
    assert "ds_data_pkl" in declared and "ds_data_pkl_2" in declared
    # both same-fnname steps present as distinct nodes
    assert "step_filter" in declared and "step_filter_2" in declared
    # graph is connected: the sink is reachable and no node is edge-orphaned
    non_sink = [d for d in declared if not d.startswith("sink_")]
    wired = {s for s, _ in edges} | {d for _, d in edges}
    assert set(non_sink) <= wired, set(non_sink) - wired


def test_include_click_uses_deduped_ref_id() -> None:
    record = {
        "dataset_paths": [],
        "dataset_hashes": [],
        "pipeline_steps": ["compare()"],
        "git_commit": "abc123",
        "includes": [
            {
                "alias": "q1",
                "job_name": "ramsey_q1",
                "node_name": "panel",
                "artifact_hash": "sha256:dead",
                "subjob_prov_dir": "run/subjobs_output/ramsey_q1/provenance",
            }
        ],
    }
    md = _mermaid_graph(record, "cmp")
    assert 'click ref_q1_panel "run/subjobs_output/ramsey_q1/provenance"' in md
    # the ref node feeds the first step
    assert "ref_q1_panel --> step_compare" in md


def test_zero_steps_wires_sources_to_sink() -> None:
    record = {
        "dataset_paths": ["d.pkl"],
        "dataset_hashes": ["sha256:aa"],
        "pipeline_steps": [],
        "git_commit": "abc123",
        "includes": [],
    }
    md = _mermaid_graph(record, "out")
    assert "ds_d_pkl --> sink_out" in md


def test_no_sources_emits_placeholder_feeding_first_step() -> None:
    record = {
        "dataset_paths": [],
        "dataset_hashes": [],
        "pipeline_steps": ["compute()"],
        "git_commit": "abc123",
        "includes": [],
    }
    md = _mermaid_graph(record, "out")
    assert "source --> step_compute" in md
