"""Offline timing probes from one private checkpoint. Never call a model."""
import argparse
import json
from pathlib import Path

from pokeagent_bench.core import action, digest
from pokeagent_bench.session import load_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--scenario', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    commands = [(direction, hold, 8) for direction in ('up', 'down', 'left', 'right') for hold in (8, 16, 48)]
    commands += [('a', 8, 24), ('b', 8, 24), (None, 60, 0)]
    for number, (button, hold, release) in enumerate(commands):
        engine, _ = load_engine(args.rom, args.scenario)
        command = action(button, hold, release, 600)
        try:
            before = engine.screenshot()
            if button:
                engine.press(button)
            for tick in range(hold + release):
                if button and tick == hold:
                    engine.release(button)
                engine.tick()
            if button:
                engine.release(button)
            after = engine.screenshot()
            (args.output / f'{number:02d}-after.png').write_bytes(after)
            results.append({'action': command, 'requested_frames': hold + release,
                            'before_sha256': digest(before), 'after_sha256': digest(after)})
        finally:
            engine.close()
    (args.output / 'calibration.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps({'probes': len(results), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
