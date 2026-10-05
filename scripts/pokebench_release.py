"""Prepare, freeze, execute and inspect a prospective PokeBench release."""
import argparse
from pathlib import Path
from pokeagent_bench import release


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    prepare=sub.add_parser('prepare')
    prepare.add_argument('--suite',type=Path,required=True)
    prepare.add_argument('--rom',type=Path,required=True)
    prepare.add_argument('--root',type=Path,required=True)
    prepare.add_argument('--variants',type=int,default=3)
    freeze=sub.add_parser('freeze')
    freeze.add_argument('--root',type=Path,required=True)
    freeze.add_argument('--models',type=Path,required=True)
    freeze.add_argument('--budget',type=int,required=True)
    freeze.add_argument('--game-data',type=Path,required=True)
    run=sub.add_parser('run')
    run.add_argument('--root',type=Path,required=True)
    run.add_argument('--rom',type=Path,required=True)
    run.add_argument('--game-data',type=Path,required=True)
    report=sub.add_parser('report')
    report.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='prepare':
        result=release.prepare(args.suite,args.rom,args.root,args.variants)
        print(result['status'])
    elif args.command=='freeze':
        result=release.freeze(args.root,release.read(args.models),args.budget,args.game_data)
        print(result['sha256'],result['planned_attempts'],result['maximum_planned_tokens'])
    elif args.command=='run':
        print(release.run(args.root,args.rom,args.game_data)['status'])
    else:
        result=release.report(args.root)
        print(result['status'],result['finished'],result['planned'],result['tokens'])


if __name__=='__main__':
    main()
