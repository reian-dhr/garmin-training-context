"""Command line: python -m garmin_context fetch | build | demo."""
import argparse
import logging
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="garmin_context", description=__doc__)
    parser.add_argument("command", choices=("fetch", "build", "demo"),
                        help="fetch: download your data; build: write context.md and dash/*.json; "
                             "demo: build from the synthetic sample data, no key needed")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(message)s", stream=sys.stderr)

    from . import metrics
    if args.command == "fetch":
        from . import fetch
        fetch.main()
    elif args.command == "build":
        metrics.main()
    else:
        sample = Path(__file__).resolve().parent.parent / "examples" / "sample_data"
        out = Path.cwd() / "demo_output"
        out.mkdir(exist_ok=True)
        metrics.main(data_dir=sample, out_dir=out, now=metrics.DEMO_NOW)
        print(f"Synthetic demo written to {out}/ (context.md and dash/)")




if __name__ == "__main__":
    main()
