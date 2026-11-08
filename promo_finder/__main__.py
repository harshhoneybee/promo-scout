import argparse
import sys
from pathlib import Path
from .parser import load_episodes
from .engine import run
from .providers import ChatProvider
from .export import save_report


def main():
    parser = argparse.ArgumentParser(description='Find timestamp-grounded microdrama promos')
    sub = parser.add_subparsers(dest='command',required=True)
    analyze = sub.add_parser('analyze',help='Analyze a ZIP, TXT or directory')
    analyze.add_argument('input')
    analyze.add_argument('--mode',choices=['baseline','ai'],default='baseline')
    analyze.add_argument('--top',type=int,default=10)
    analyze.add_argument('--out',required=True,help='New output directory (must not exist)')
    serve = sub.add_parser('serve',help='Open the local browser prototype')
    serve.add_argument('--port',type=int,default=8765)
    args = parser.parse_args()
    if args.command == 'serve':
        from .server import serve as start
        start(args.port)
        return
    try:
        if Path(args.out).exists():
            raise ValueError('Output directory already exists; choose a new path to preserve previous raw outputs')
        episodes = load_episodes(args.input)
        provider = ChatProvider.from_env() if args.mode=='ai' else None
        report = run(episodes,args.mode,args.top,provider,
            progress=lambda n,total,r:print(f'[{n}/{total}] Episode {r["episode"]}: {r["candidates_valid"]} valid' + (' — ERROR' if r['error'] else ''),file=sys.stderr))
        save_report(report,args.out)
        print(f'Saved {len(report["promos"])} ranked promos to {args.out}')
        print(report['meta']['warning'])
        if report['meta']['episodes_succeeded'] != len(episodes):
            print('Partial run: inspect episode errors in results.json',file=sys.stderr)
            sys.exit(2)
    except (ValueError,RuntimeError,OSError) as exc:
        parser.exit(1,f'Error: {exc}\n')


if __name__=='__main__':
    main()
