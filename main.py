from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

import pandas as pd

from core.runner import run_job
from loaders.registry import _LOADER_REGISTRY, load
from plots.targets import RENDER_TARGETS
from provenance import hash_string

try:
    import h5py
except ImportError:
    h5py = None


def _module_from_path(path: Path):
    module_name = f"job_{re.sub(r'[^A-Za-z0-9_]', '_', path.stem)}_{hash_string(str(path.resolve()))[:8]}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot import job module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    job = getattr(module, "job", None)
    if job is not None:
        setattr(job, "job_file", path.resolve())
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
        safe_column = re.sub(r"[^A-Za-z0-9_]", "_", str(column))
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
    run_parser.add_argument(
        "--reuse-deps",
        action="store_true",
        help="For composite jobs: reuse included sub-jobs' cached artifacts instead of re-running them.",
    )
    run_parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Base directory for resolving relative dataset paths (e.g. 'tool/datasets/...').",
    )

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("job_file", nargs="?")

    wizard_parser = subparsers.add_parser("schema-wizard")
    wizard_parser.add_argument("file")

    args = parser.parse_args()
    if args.command == "run":
        data_root = (
            Path(args.data_root).expanduser().resolve() if args.data_root else None
        )
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
                run_job(
                    _module_from_path(job_file).job,
                    Path("output"),
                    force=args.force,
                    data_root=data_root,
                    reuse_deps=args.reuse_deps,
                )
            return
        if not args.path:
            parser.error("run requires a path unless --all is set")
        run_job(
            _module_from_path(Path(args.path)).job,
            Path("output"),
            force=args.force,
            data_root=data_root,
            reuse_deps=args.reuse_deps,
        )
        return
    if args.command == "inspect":
        print("Loaders:", ", ".join(sorted(_LOADER_REGISTRY)))
        print("Targets:", ", ".join(sorted(RENDER_TARGETS)))
        if args.job_file:
            _print_job(_module_from_path(Path(args.job_file)).job)
        return
    if args.command == "schema-wizard":
        file_path = Path(args.file)

        # Special handling for HDF5 files with multiple datasets
        if file_path.suffix.lower() in {".h5", ".hdf5"} and h5py:
            with h5py.File(file_path, "r") as f:
                keys = list(f.keys())
                if len(keys) > 1:
                    print(f"Multiple datasets found: {', '.join(keys)}\n")
                    for key in keys:
                        print(f"\n{'=' * 60}")
                        print(f"Dataset: {key}")
                        print("=" * 60)
                        dataset = f[key]
                        data = dataset[()]
                        if len(data.shape) == 2:
                            df = pd.DataFrame(data)
                        elif len(data.shape) == 1:
                            df = pd.DataFrame({key: data})
                        else:
                            print(f"Unsupported shape: {data.shape}")
                            continue
                        _schema_stub(df)
                    return

        _schema_stub(load(file_path))


if __name__ == "__main__":
    main()
