from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

from core.runner import run_job
from loaders.registry import _LOADER_REGISTRY, load
from plots.targets import RENDER_TARGETS
from provenance import hash_string


def _module_from_path(path: Path):
    module_name = f"job_{re.sub(r'[^A-Za-z0-9_]', '_', path.stem)}_{hash_string(str(path.resolve()))[:8]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot import job module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _print_job(job) -> None:
    for node_id, node in job.dag.items():
        inputs = ", ".join(handle.node_id for handle in node.inputs) or "-"
        print(f"{node_id}: {node.fn.__name__} <- [{inputs}] {node.kwargs}")


def _dtype_stub(dtype) -> str:
    kind = getattr(dtype, "kind", None)
    if kind in {"i", "u"}:
        return "int"
    if kind == "f":
        return "float"
    if kind == "b":
        return "bool"
    if str(dtype).startswith("datetime64"):
        return "pd.Timestamp"
    return "str"


def _schema_stub(frame) -> None:
    print(frame.dtypes.to_string())
    print("import pandas as pd")
    print("import pandera as pa")
    print("from pandera.typing import Series")
    print()
    print("class InferredSchema(pa.DataFrameModel):")
    for column, dtype in frame.dtypes.items():
        safe_column = re.sub(r"[^A-Za-z0-9_]", "_", column)
        if safe_column and safe_column[0].isdigit():
            safe_column = f"_{safe_column}"
        print(f"    {safe_column}: Series[{_dtype_stub(dtype)}]")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("path", nargs="?")
    run_parser.add_argument("--all", action="store_true")
    run_parser.add_argument("--include-archived", action="store_true")
    run_parser.add_argument("--force", action="store_true")

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("job_file", nargs="?")

    wizard_parser = subparsers.add_parser("schema-wizard")
    wizard_parser.add_argument("file")

    args = parser.parse_args()
    if args.command == "run":
        if args.all:
            job_files = [
                job_file
                for job_file in sorted(Path("jobs/active").glob("*.py"))
                if job_file.name != "__init__.py"
            ]
            if args.include_archived:
                job_files.extend(
                    job_file
                    for job_file in sorted(Path("jobs/archived").glob("*.py"))
                    if job_file.name != "__init__.py"
                )
            for job_file in job_files:
                print("\n\n---------------------\nRunning job from", job_file)
                run_job(_module_from_path(job_file).job, Path("output"), force=args.force)
            return
        if not args.path:
            parser.error("run requires a path unless --all is set")
        run_job(_module_from_path(Path(args.path)).job, Path("output"), force=args.force)
        return
    if args.command == "inspect":
        print("Loaders:", ", ".join(sorted(_LOADER_REGISTRY)))
        print("Targets:", ", ".join(sorted(RENDER_TARGETS)))
        if args.job_file:
            _print_job(_module_from_path(Path(args.job_file)).job)
        return
    _schema_stub(load(Path(args.file)))


if __name__ == "__main__":
    main()
