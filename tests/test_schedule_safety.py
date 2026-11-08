import plistlib
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts import setup_api_schedule


@pytest.fixture
def tmp_path():
    with TemporaryDirectory(prefix='schedule-safety-', dir=setup_api_schedule.ROOT) as path:
        yield Path(path)


def _write_agent(path, label, working_directory):
    path.write_bytes(plistlib.dumps({'Label': label, 'WorkingDirectory': str(working_directory)}))


def test_uninstall_preserves_same_named_foreign_agent(tmp_path, monkeypatch):
    project = tmp_path/'this-project'
    other_project = tmp_path/'other-project'
    project.mkdir()
    other_project.mkdir()
    agents = tmp_path/'LaunchAgents'
    agents.mkdir()
    label = 'vn.khdl.tennis.daily'
    target = agents/f'{label}.plist'
    _write_agent(target, label, other_project)
    commands = []
    monkeypatch.setattr(setup_api_schedule, 'ROOT', project)

    setup_api_schedule.uninstall(agents, lambda *a, **k: commands.append(a))

    assert target.exists()
    assert commands == []


def test_uninstall_removes_verified_project_agent(tmp_path, monkeypatch):
    project = tmp_path/'this-project'
    project.mkdir()
    agents = tmp_path/'LaunchAgents'
    agents.mkdir()
    label = 'vn.khdl.tennis.daily'
    target = agents/f'{label}.plist'
    _write_agent(target, label, project)
    commands = []
    monkeypatch.setattr(setup_api_schedule, 'ROOT', project)
    monkeypatch.setattr(setup_api_schedule.os, 'getuid', lambda: 501, raising=False)

    setup_api_schedule.uninstall(agents, lambda *a, **k: commands.append(a))

    assert not target.exists()
    assert commands == [(['launchctl', 'bootout', f'gui/501/{label}'],)]
