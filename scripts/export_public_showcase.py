"""Build the public PokeBench showcase from the local showcase in a new directory."""
import argparse
from pokeagent_bench.showcase import export_public

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--web', required=True, help='Local showcase directory with showcase-data.json')
parser.add_argument('--output', required=True, help='New output directory')
parser.add_argument('--report', help='Reviewed technical report PDF to include')
args = parser.parse_args()
data = export_public(args.web, args.output, report=args.report)
print(data['updated_at'], data['short']['finished'], '/', data['short']['planned'])
