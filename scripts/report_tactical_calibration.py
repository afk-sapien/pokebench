"""Publish complete offline calibration evidence without adding model leaderboard rows."""
import argparse
import html
from pathlib import Path

from pokeagent_bench.core import write_json
from pokeagent_bench.suite import read
from pokeagent_bench.tactical_validation import assess


def publish(roots, output, diagnostic=None):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    reports = []
    sections = []
    for root in map(Path, roots):
        report = assess(root)
        registration = read(root/'preregistration.json')
        candidate = registration['candidate']
        write_json(root/'assessment.json', report)
        reports.append({'candidate':candidate, **report})
        wins = report['wins']
        rows = ''.join(f'<tr><td>{html.escape(mode)}</td><td>{count}/{report["attempts_per_policy"]}</td></tr>'
                       for mode, count in wins.items())
        cells = ''.join(f'<tr><td>{html.escape(row["scenario"])}</td><td>{html.escape(row["mode"])}</td>'
                        f'<td>{"Win" if row["completed"] else "Loss"}</td><td>{row["decisions"]}</td>'
                        f'<td>{html.escape(row["reason"])}</td></tr>' for row in report['rows'])
        sections.append(f'<section><h2>{html.escape(candidate)}</h2><p><strong>{html.escape(report["status"])}</strong>. '
                        f'{html.escape(report["message"])}</p><table><tr><th>Frozen policy</th><th>Wins</th></tr>{rows}</table>'
                        f'<p>{report["unique_tactical_trajectories"]} distinct tactical trajectories. '
                        f'{report["invalid_actions"]} invalid actions. Every trial replay verified.</p>'
                        f'<p>Policy SHA256: <code>{report["policy_sha256"]}</code></p>'
                        f'<details><summary>All {len(report["rows"])} trial outcomes</summary><table>'
                        f'<tr><th>Starting position</th><th>Policy</th><th>Outcome</th><th>Decisions</th><th>Stop reason</th></tr>'
                        f'{cells}</table></details></section>')
    diagnostic_data = None
    if diagnostic:
        protocol = read(Path(diagnostic)/'protocol.json')
        result = read(Path(diagnostic)/'result.json')
        if protocol.get('eligible_for_calibration_score') is not False or not result['replay']['verified']:
            raise ValueError('Diagnostic must be explicitly unscored and replay verified')
        diagnostic_data = {'protocol':protocol, 'result':result}
        outcome = 'won' if result['completed'] else 'lost'
        sections.append('<section><h2>The remaining loss</h2><p>The frozen policy lost start 031 after '
                        'paralysis, confusion, a critical hit and delayed healing. A later diagnostic '
                        'used Rest earlier to cure paralysis and '+outcome+' from that same start.</p>'
                        '<p>This was designed after inspecting the loss. It is excluded from the score, '
                        'which remains 31/32. It shows that the start is winnable. It does not establish '
                        'a perfect policy or isolate luck from decision quality, since action timing affects RNG.</p></section>')
    write_json(output.with_suffix('.json'), {'model_calls':0,'reports':reports,'posthoc_diagnostic':diagnostic_data})
    body = '\n'.join(sections)
    output.write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tactical battle calibration</title><style>
body {{ font: 17px/1.6 system-ui, sans-serif }}
main {{ max-width: 980px }}
body, main, section, table {{ margin: 2rem auto }}
main {{ padding: 0 1rem }}
th, td {{ padding: .35rem 1rem }}
th, td {{ text-align: left }}
code {{ overflow-wrap: anywhere }}
summary {{ cursor: pointer }}
</style><main><a href="pokemon-benchmarks.html">Back to benchmarks</a><h1>Tactical battle calibration</h1>
<p>Offline controller policies, zero model calls. These outcomes do not enter model rankings.</p>
<p>The acceptance rule was frozen before the first holdout: at least 29 tactical wins in 32 starts,
at least 13 more wins than each attack baseline, no invalid actions, and complete replay evidence.
The second candidate uses fresh starting offsets that exclude the first holdout.</p>
<p>These are reproducible timing variants. They are not proven independent RNG samples.
A perfect observed record does not guarantee a perfect win probability or optimal play.
The policies observe only the public game interface. They cannot inspect enemy memory or future RNG.</p>
<p>All trials count. No best-of selection, battle reloads, or strategy selection after seeing each outcome.</p>
<p><a href="{html.escape(output.with_suffix('.json').name)}">Download full calibration results (JSON)</a></p>
{body}</main></html>''')
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('roots', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--diagnostic', type=Path)
    args = parser.parse_args()
    publish(args.roots, args.output, args.diagnostic)


if __name__ == '__main__':
    main()
