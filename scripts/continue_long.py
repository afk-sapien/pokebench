"""Create a separately recorded Long extension without starting model requests."""
import argparse
import json
from pokeagent_bench.long_runs import create_continuation

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--parent', required=True)
parser.add_argument('--output', required=True)
parser.add_argument('--additional-decisions', type=int, default=2000)
args = parser.parse_args()
print(json.dumps(create_continuation(args.parent, args.output,
                                    additional_decisions=args.additional_decisions), indent=2))
