"""Render launchd schedules; install only after a local API key is configured."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import json

ROOT=Path(__file__).resolve().parents[1]


def render():
    python=ROOT/'.venv/bin/python'
    if not python.exists():
        raise RuntimeError('Create the project .venv first')
    logs=ROOT/'logs';logs.mkdir(exist_ok=True)
    dest=ROOT/'runs/scheduler';dest.mkdir(parents=True,exist_ok=True)
    jobs=[]
    unified=json.loads((ROOT/'config/unified.json').read_text())['weekly_schedule']
    for label,script,extra,schedule in [
        ('vn.khdl.tennis.daily','run_api_batch.py',[],{'StartCalendarInterval':{'Hour':7,'Minute':10}}),
        ('vn.khdl.tennis.weekly','run_unified_load.py',['--collect','--refresh-reference'],
            {'StartCalendarInterval':{'Weekday':unified['weekday'],'Hour':unified['hour'],'Minute':unified['minute']}}),
        ('vn.khdl.tennis.alerts','telegram_alerts.py',['--flush'],{'StartInterval':600})]:
        payload={'Label':label,'ProgramArguments':[str(python),str(ROOT/'scripts'/script),*extra],
                 'WorkingDirectory':str(ROOT),**schedule,
                 'StandardOutPath':str(logs/f'{label}.log'),'StandardErrorPath':str(logs/f'{label}.error.log'),
                 'EnvironmentVariables':{'PYTHONUNBUFFERED':'1'},'RunAtLoad':False}
        path=dest/f'{label}.plist'
        path.write_bytes(plistlib.dumps(payload))
        jobs.append(path)
    return jobs


def uninstall(target_root=None, run_command=None):
    target_root=Path(target_root) if target_root is not None else Path.home()/'Library/LaunchAgents'
    run_command=run_command or subprocess.run
    for label in ['vn.khdl.tennis.daily','vn.khdl.tennis.weekly','vn.khdl.tennis.alerts']:
        target=target_root/f'{label}.plist'
        if not target.exists():
            continue
        try:
            payload=plistlib.loads(target.read_bytes())
        except (OSError,plistlib.InvalidFileException,ValueError):
            print(f'Refusing to remove {target}: plist cannot be verified as project-owned.',file=sys.stderr)
            continue
        owner=payload.get('WorkingDirectory')
        try:
            owned=payload.get('Label')==label and owner is not None and Path(owner).resolve()==ROOT.resolve()
        except (OSError,RuntimeError):
            owned=False
        if not owned:
            print(f'Refusing to remove {target}: ownership metadata does not match this project.',file=sys.stderr)
            continue
        run_command(['launchctl','bootout',f'gui/{os.getuid()}/{label}'],capture_output=True)
        target.unlink()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--install',action='store_true',help='Install generated jobs for this macOS user, after key presence check')
    p.add_argument('--uninstall',action='store_true',help='Disable the project-owned ingestion and alert-delivery agents')
    args=p.parse_args()
    if args.install and args.uninstall:
        p.error('Choose install or uninstall')
    if args.uninstall:
        if sys.platform!='darwin':
            raise RuntimeError('launchd requires macOS')
        uninstall()
        print('Project schedules disabled; data retained.')
        return
    jobs=render()
    for path in jobs:
        print('Rendered:',path)
    if not args.install:
        print('Schedules prepared but NOT active. Daily 07:10, Monday 07:40 (local); Telegram outbox every 10 minutes.')
        return
    if sys.platform!='darwin':
        raise RuntimeError('launchd installation requires macOS; use cron on Linux')
    check=subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/run_api_batch.py'),'--check'],capture_output=True,text=True)
    if check.returncode:
        raise RuntimeError('API key not configured. Set .env and test a live batch before enabling schedules.')
    # Prevent replacing another application/user-created job with the same label.
    target_root=Path.home()/'Library/LaunchAgents';target_root.mkdir(parents=True,exist_ok=True)
    for job in jobs:
        target=target_root/job.name
        if target.exists() and plistlib.loads(target.read_bytes()).get('WorkingDirectory')!=str(ROOT):
            raise RuntimeError('Existing launch agent has a different owner directory; refusing replacement')
    for job in jobs:
        target=target_root/job.name
        if target.exists() and target.read_bytes()==job.read_bytes():
            loaded=subprocess.run(['launchctl','print',f'gui/{os.getuid()}/{job.stem}'],capture_output=True)
            if loaded.returncode==0:
                print('Already active:',target)
                continue
        target.write_bytes(job.read_bytes())
        subprocess.run(['launchctl','bootout',f'gui/{os.getuid()}',str(target)],capture_output=True)
        subprocess.run(['launchctl','bootstrap',f'gui/{os.getuid()}',str(target)],check=True,capture_output=True)
        print('Installed:',target)
    print('Active while the user session is available; machine timezone must be Asia/Ho_Chi_Minh for the intended local schedule.')


if __name__=='__main__':
    try:
        main()
    except (RuntimeError,subprocess.CalledProcessError) as exc:
        print(f'Schedule setup stopped: {exc}',file=sys.stderr)
        sys.exit(1)
