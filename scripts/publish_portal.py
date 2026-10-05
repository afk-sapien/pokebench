"""Refresh the read-only benchmark portal without changing running evaluations."""
import argparse
import json
from pathlib import Path
import time
import traceback

from pokeagent_bench.portal import publish


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--watch-seconds', type=int, default=0)
    args = parser.parse_args()
    if args.watch_seconds and args.watch_seconds < 10:
        parser.error('Refresh interval must be at least ten seconds')
    config = json.loads(args.config.read_text())
    while True:
        try:
            result = publish(config, args.output)
            print(result['updated_at'], result['cohorts'][0]['phase'], flush=True)
        except Exception:
            if not args.watch_seconds:
                raise
            traceback.print_exc()
        if not args.watch_seconds:
            break
        time.sleep(args.watch_seconds)


if __name__ == '__main__':
    main()
