"""Add one 2000-decision chunk to a decision-capped Long run, without starting model requests."""
import argparse
import json
from pokeagent_bench.long_runs import create_continuation

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
print(json.dumps(create_continuation(args.parent, args.output), indent=2))
