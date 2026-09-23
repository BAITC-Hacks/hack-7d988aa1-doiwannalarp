import argparse
import time
from pathlib import Path

from moneygraph import pipeline


def main():
    parser = argparse.ArgumentParser(description="Run the MoneyGraph pipeline.")
    parser.add_argument("--data", default="data")
    parser.add_argument("--out", default="outputs")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    meta = pipeline.run(data_dir=args.data, out_dir=args.out, seed=args.seed)
    elapsed = time.perf_counter() - t0

    print("Output paths:")
    for name, path in meta["output_paths"].items():
        print(f"  {name}: {path}")
    print(f"run_meta.json: {out_dir / 'run_meta.json'}")
    print(f"Total elapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
