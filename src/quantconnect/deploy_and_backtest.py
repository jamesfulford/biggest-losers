"""
Push a C# LEAN algorithm to QuantConnect Cloud, compile it, run a backtest, and
save the resulting statistics + equity curve locally.

Usage:
    python3 -m src.quantconnect.deploy_and_backtest \
        --project-name minion-nrgu \
        --source-dir quantconnect/Minion \
        --backtest-name "minion baseline"
"""
import argparse
import json
import pathlib

from src.quantconnect import client
from src.outputs.pathing import get_paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--source-dir", required=True,
                         help="Directory containing the .cs file(s) to upload")
    parser.add_argument("--backtest-name", required=True)
    parser.add_argument("--project-id", type=int, default=None,
                         help="Reuse an existing project instead of creating a new one")
    args = parser.parse_args()

    if args.project_id is not None:
        project_id = args.project_id
        print(f"Reusing project {project_id}")
    else:
        created = client.create_project(args.project_name)
        project_id = created["projects"][0]["projectId"]
        print(f"Created project {project_id} ({args.project_name})")
        # new projects come with a default Main.cs stub, which would collide
        # with our own QCAlgorithm subclass at compile time
        try:
            client.delete_file(project_id, "Main.cs")
        except RuntimeError:
            pass

    source_dir = pathlib.Path(args.source_dir)
    for cs_file in source_dir.glob("*.cs"):
        content = cs_file.read_text()
        try:
            client.create_file(project_id, cs_file.name, content)
            print(f"Created file {cs_file.name}")
        except RuntimeError:
            client.update_file(project_id, cs_file.name, content)
            print(f"Updated file {cs_file.name}")

    compile_result = client.create_compile(project_id)
    compile_id = compile_result["compileId"]
    compile_result = client.wait_for_compile(project_id, compile_id)
    if compile_result["state"] != "BuildSuccess":
        raise RuntimeError(f"Compile failed: {json.dumps(compile_result, indent=2)}")
    print(f"Compiled successfully ({compile_id})")

    backtest_result = client.create_backtest(project_id, compile_id, args.backtest_name)
    backtest_id = backtest_result["backtest"]["backtestId"]
    print(f"Backtest running ({backtest_id})...")
    backtest = client.wait_for_backtest(project_id, backtest_id)

    output_dir = pathlib.Path(get_paths()["data"]["outputs"]["dir"]) / "quantconnect" / args.project_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{backtest_id}.json"
    output_path.write_text(json.dumps(backtest, indent=2))
    print(f"Saved backtest results to {output_path}")

    statistics = backtest.get("statistics", {})
    for key, value in statistics.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
