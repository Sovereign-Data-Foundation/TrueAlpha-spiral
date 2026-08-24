import pytest
from unittest.mock import MagicMock
from tas_pythonetics.git_safety import GitStateMonitor, GitActionGuard

def test_guard():
    monitor = GitStateMonitor()
    guard = GitActionGuard(monitor)

    assert guard.authorize_command("git diff --ext-cmd=calc status") is False
    assert guard.authorize_command("git switch -c new_branch") is True
    assert guard.authorize_command("git log -p") is True
    assert guard.authorize_command("git -c core.hooksPath=/tmp commit -m 'msg'") is False
    assert guard.authorize_command("git commit -c HEAD") is True
