"""`enter --model X --suite NAME`: estimate, ask, run with resume, pack the bundle and link a prefilled issue.

This only chains run --suite and submit. The same command resumes an unfinished run.
"""
from urllib.parse import urlencode

from .quick_run import run_suite
from .submission import submit, verify

ISSUES = 'https://github.com/afk-sapien/pokebench/issues/new'


def ask():
    try:
        answer = input('Start the run? [y/N] ')
    except EOFError:
        answer = ''
    return answer.strip().lower() in ('y', 'yes')


def issue_link(model, suite):
    return ISSUES + '?' + urlencode({'template': 'run-submission.md', 'title': f'Run submission: {model}, {suite}'})


def enter(args):
    if args.suite != 'smoke':
        print(f'Credit: GitHub handle {args.handle}' if args.handle else
              'Credit: none. Add --handle YOUR_GITHUB_NAME to be named on the leaderboard row', flush=True)
    ran = run_suite(args, ask=None if args.yes else ask, next_step=False)
    if ran is None:
        return None
    output, result, rom, fixtures = ran
    if any(cell['state'] != 'finished' for cell in result['cells']):
        print('Nothing was packed because not every run finished. Run the same enter command again to continue.',
              flush=True)
        return None
    bundle = output.with_name(output.name + '.pokebench.zip')
    if bundle.exists():
        print(f'{bundle} is already packed. Delete it and run the same enter command to pack it again.', flush=True)
    else:
        submit(output, bundle, handle=args.handle, attempts=args.attempts)
    if args.suite == 'smoke':
        verify(bundle, rom, fixtures)
        print('Your setup and the submission path work. A smoke bundle is a setup check and never a leaderboard '
              'entry, so do not open an issue for it.', flush=True)
        return None
    model = result['models'][0]['model']
    print(f'\nNext, open a submission issue and attach {bundle}:\n  {issue_link(model, args.suite)}\n'
          'Fill in the fields the issue asks for. The maintainer replays the bundle and replies on the issue.',
          flush=True)
    return None
