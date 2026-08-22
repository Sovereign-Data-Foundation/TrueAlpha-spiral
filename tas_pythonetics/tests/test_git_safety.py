import pytest
from unittest.mock import MagicMock
from tas_pythonetics.git_safety import GitStateMonitor, GitActionGuard

def test_check_invariant_clean():
    monitor = GitStateMonitor()
    monitor.get_current_branch = MagicMock(return_value="main")
    monitor.is_clean_state = MagicMock(return_value=True)

    assert monitor.check_invariant("NO_DETACHED_HEAD") is True
    assert monitor.check_invariant("CLEAN_WORKING_DIR") is True

def test_check_invariant_detached():
    monitor = GitStateMonitor()
    monitor.get_current_branch = MagicMock(return_value="DETACHED_HEAD")

    assert monitor.check_invariant("NO_DETACHED_HEAD") is False

def test_guard_blocks_destructive_commands():
    monitor = GitStateMonitor()
    monitor.get_current_branch = MagicMock(return_value="feature-branch")
    guard = GitActionGuard(monitor)

    assert guard.authorize_command("git push --force") is False
    assert guard.authorize_command("git push -f origin main") is False
    assert guard.authorize_command("git reset --hard HEAD~1") is False

def test_guard_blocks_push_to_protected():
    monitor = GitStateMonitor()
    monitor.get_current_branch = MagicMock(return_value="main")
    guard = GitActionGuard(monitor)

    # Should block direct push to main
    assert guard.authorize_command("git push origin main") is False

    # Should allow non-push commands
    assert guard.authorize_command("git status") is True

def test_guard_allows_safe_operations():
    monitor = GitStateMonitor()
    monitor.get_current_branch = MagicMock(return_value="feature-branch")
    guard = GitActionGuard(monitor)

    assert guard.authorize_command("git add .") is True
    assert guard.authorize_command("git commit -m 'fix'") is True
    assert guard.authorize_command("git push origin feature-branch") is True

def test_guard_blocks_non_git_commands():
    monitor = GitStateMonitor()
    guard = GitActionGuard(monitor)
    assert guard.authorize_command("rm -rf /") is False
    assert guard.authorize_command("echo hello") is False
    assert guard.authorize_command("./malicious_script.sh") is False

def test_guard_blocks_path_based_git_execution():
    monitor = GitStateMonitor()
    guard = GitActionGuard(monitor)
    assert guard.authorize_command("./git status") is False
    assert guard.authorize_command("/usr/bin/git push origin main") is False
    assert guard.authorize_command("malicious_dir/git status") is False
    assert guard.authorize_command("../git commit") is False

def test_guard_blocks_dangerous_global_options():
    monitor = GitStateMonitor()
    guard = GitActionGuard(monitor)
    assert guard.authorize_command("git -c core.pager=calc status") is False
    assert guard.authorize_command("git -ccore.pager=calc status") is False
    assert guard.authorize_command("git --exec-path=/tmp status") is False
    assert guard.authorize_command("git --paginate status") is False
    assert guard.authorize_command("git config core.pager calc") is False
    assert guard.authorize_command("git -p status") is False
    assert guard.authorize_command("git -pstatus") is False
    assert guard.authorize_command("git log -p") is True
    assert guard.authorize_command("git --config-env=core.pager=PAGER_ENV status") is False

def test_guard_blocks_remote_pack_execution():
    monitor = GitStateMonitor()
    guard = GitActionGuard(monitor)
    assert guard.authorize_command("git clone --upload-pack=calc git://a") is False
    assert guard.authorize_command("git clone --receive-pack=calc git://a") is False
    assert guard.authorize_command("git clone -u calc git://a") is False
    assert guard.authorize_command("git clone -ucalc git://a") is False

def test_guard_blocks_complex_force_pushes():
    monitor = GitStateMonitor()
    monitor.get_current_branch = MagicMock(return_value="feature-branch")
    guard = GitActionGuard(monitor)

    assert guard.authorize_command("git push origin --force-with-lease") is False
    assert guard.authorize_command("git push origin +main") is False
    assert guard.authorize_command("git push origin --force") is False
    assert guard.authorize_command("git push --force origin") is False

def test_guard_allows_safe_plus_in_other_commands():
    monitor = GitStateMonitor()
    monitor.get_current_branch = MagicMock(return_value="feature-branch")
    guard = GitActionGuard(monitor)

    # Adding a file with + in name should be allowed
    assert guard.authorize_command("git add +filename.txt") is True

def test_guard_blocks_process_substitution():
    monitor = GitStateMonitor()
    guard = GitActionGuard(monitor)
    assert guard.authorize_command("git push origin <(echo main)") is False
    assert guard.authorize_command("git add >(tee log.txt)") is False
    assert guard.authorize_command("git push origin $(echo main)") is False
    assert guard.authorize_command(f"git push origin {chr(96)}echo main{chr(96)}") is False

def test_guard_blocks_dangerous_options_post_subcommand():
    monitor = GitStateMonitor()
    guard = GitActionGuard(monitor)
    # Check that post-subcommand options are blocked
    assert guard.authorize_command("git clone -c core.pager=calc origin") is False
    assert guard.authorize_command("git clone --config core.pager=calc origin") is False
    assert guard.authorize_command("git difftool --ext-cmd=calc") is False
    assert guard.authorize_command("git clone --config-env=core.pager=PAGER origin") is False

    # Check that -p is allowed only for log, diff, show
    assert guard.authorize_command("git log -p") is True
    assert guard.authorize_command("git diff -p") is True
    assert guard.authorize_command("git show -p") is True

    # Check that -p is blocked for other subcommands
    assert guard.authorize_command("git status -p") is False
    assert guard.authorize_command("git init -p") is False


def test_guard_allows_safe_c_and_p():
    monitor = GitStateMonitor()
    guard = GitActionGuard(monitor)

    # Safe -c uses
    assert guard.authorize_command("git switch -c new_branch") is True
    assert guard.authorize_command("git checkout -c new_branch") is True
    assert guard.authorize_command("git commit -c HEAD") is True

    # Safe -p uses
    assert guard.authorize_command("git add -p") is True
    assert guard.authorize_command("git commit -p") is True
    assert guard.authorize_command("git checkout -p") is True
    assert guard.authorize_command("git reset -p") is True
    assert guard.authorize_command("git stash -p") is True

def test_guard_allows_safe_long_options_starting_with_c_p():
    monitor = GitStateMonitor()
    guard = GitActionGuard(monitor)

    # Safe --c and --p uses
    assert guard.authorize_command("git rm --cached") is True
    assert guard.authorize_command("git status --porcelain") is True
    assert guard.authorize_command("git branch --contains") is True
    assert guard.authorize_command("git merge --continue") is True
