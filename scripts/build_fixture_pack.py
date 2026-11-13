"""Maintainer tool: pack a validated private fixture root for `pokebench setup`.

The pack is compressed against the ROM, so it cannot be opened without that ROM.
"""
import argparse
import json
from pathlib import Path

from pokeagent_bench.local_setup import PACK, build_pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--fixtures', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=PACK)
    args = parser.parse_args()
    print(json.dumps(build_pack(args.rom, args.fixtures, args.output), indent=2))


if __name__ == '__main__':
    main()
