import pytest
from unittest.mock import MagicMock
from tas_pythonetics.git_safety import (
    GitStateMonitor, GitActionGuard, StateTransition, TransitionImpact,
)

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
    assert guard.authorize_command("git --exec-path=/tmp status") is False
    assert guard.authorize_command("git --paginate status") is False
    assert guard.authorize_command("git config core.pager calc") is False
    assert guard.authorize_command("git -p status") is False
    assert guard.authorize_command("git log -p") is True

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

def test_guard_blocks_config_env_injection():
    """--config-env must be blocked: it allows arbitrary configuration via environment
    variables (e.g. core.pager), bypassing the -c filter and enabling RCE."""
    monitor = GitStateMonitor()
    guard = GitActionGuard(monitor)
    # Inline value form: --config-env=core.pager=MY_PAGER
    assert guard.authorize_command("git --config-env=core.pager=MY_PAGER log") is False
    # Separate value form: --config-env core.pager=MY_PAGER
    assert guard.authorize_command("git --config-env core.pager=MY_PAGER status") is False
    # Mixed-case variant
    assert guard.authorize_command("git --Config-Env=core.pager=cmd status") is False
    # Ensure safe commands are still allowed after the above checks
    assert guard.authorize_command("git log --oneline") is True

def test_guard_own_integrity():
    """integrity controls itself: the guard must be able to verify its own invariants."""
    # Must not raise
    GitActionGuard.verify_own_integrity()

def test_protected_branches_are_immutable():
    """PROTECTED_BRANCHES must be a frozenset so the guard's boundary cannot be
    silently widened at runtime."""
    assert isinstance(GitActionGuard.PROTECTED_BRANCHES, frozenset)


# ---------------------------------------------------------------------------
# State-transition boundary: classify_transition tests
#
# These tests verify the explicit S_current + Action → S_candidate model.
# Each test asserts both the impact class and the admissibility decision so
# that the guard is tested as a transition evaluator, not merely a token filter.
# ---------------------------------------------------------------------------

def _guard(branch="feature-branch"):
    monitor = GitStateMonitor()
    monitor.get_current_branch = MagicMock(return_value=branch)
    return GitActionGuard(monitor)


def test_state_transition_is_frozen():
    """StateTransition must be immutable: it is a decision record, not mutable state."""
    t = StateTransition("log", TransitionImpact.READ_ONLY, True, "read_only_admitted")
    with pytest.raises((AttributeError, TypeError)):
        t.admissible = False  # type: ignore[misc]


def test_classify_read_only_operations():
    """Read-only subcommands produce READ_ONLY impact and are admissible."""
    guard = _guard()
    for cmd in ("git log", "git status", "git diff HEAD", "git show HEAD",
                "git ls-files", "git fetch origin", "git blame README.md"):
        t = guard.classify_transition(cmd)
        assert t.impact == TransitionImpact.READ_ONLY, cmd
        assert t.admissible is True, cmd
        assert t.reason == "read_only_admitted", cmd


def test_classify_local_safe_operations():
    """Local, reversible operations produce LOCAL_SAFE impact and are admissible."""
    guard = _guard()
    for cmd in ("git add .", "git commit -m 'fix'", "git checkout main",
                "git stash", "git merge origin/main", "git tag v1.0"):
        t = guard.classify_transition(cmd)
        assert t.impact == TransitionImpact.LOCAL_SAFE, cmd
        assert t.admissible is True, cmd


def test_classify_local_destructive_operations():
    """LOCAL_DESTRUCTIVE transitions are refused — history impact without remote proof."""
    guard = _guard()
    hard_reset = guard.classify_transition("git reset --hard HEAD~1")
    assert hard_reset.impact == TransitionImpact.LOCAL_DESTRUCTIVE
    assert hard_reset.admissible is False
    assert hard_reset.reason == "local_destructive_prohibited"
    assert hard_reset.subcommand == "reset"

    clean = guard.classify_transition("git clean -fd")
    assert clean.impact == TransitionImpact.LOCAL_DESTRUCTIVE
    assert clean.admissible is False


def test_classify_lineage_rewrite_operations():
    """LINEAGE_REWRITE transitions are refused — provenance cannot be preserved."""
    guard = _guard()
    rebase = guard.classify_transition("git rebase main")
    assert rebase.impact == TransitionImpact.LINEAGE_REWRITE
    assert rebase.admissible is False
    assert rebase.reason == "lineage_rewrite_prohibited"
    assert rebase.subcommand == "rebase"

    amend = guard.classify_transition("git commit --amend --no-edit")
    assert amend.impact == TransitionImpact.LINEAGE_REWRITE
    assert amend.admissible is False
    assert amend.subcommand == "commit"


def test_classify_remote_mutation_admissible():
    """A safe push from a non-protected branch is REMOTE_MUTATION and admissible."""
    guard = _guard(branch="feature-x")
    t = guard.classify_transition("git push origin feature-x")
    assert t.impact == TransitionImpact.REMOTE_MUTATION
    assert t.admissible is True
    assert t.reason == "remote_mutation_admitted"
    assert t.subcommand == "push"


def test_classify_remote_mutation_refused_on_protected_branch():
    """Push from a protected branch is REMOTE_MUTATION but not admissible."""
    for branch in ("main", "master", "production"):
        guard = _guard(branch=branch)
        t = guard.classify_transition("git push origin " + branch)
        assert t.impact == TransitionImpact.REMOTE_MUTATION, branch
        assert t.admissible is False, branch
        assert branch in t.reason, branch


def test_classify_remote_destructive_operations():
    """REMOTE_DESTRUCTIVE transitions are refused regardless of branch."""
    guard = _guard()
    cases = [
        "git push --force",
        "git push -f origin main",
        "git push origin --force-with-lease",
        "git push origin +main",
        "git push --delete origin feature",
    ]
    for cmd in cases:
        t = guard.classify_transition(cmd)
        assert t.impact == TransitionImpact.REMOTE_DESTRUCTIVE, cmd
        assert t.admissible is False, cmd
        assert t.reason == "remote_destructive_prohibited", cmd


def test_classify_forbidden_injection_vectors():
    """Injection attempts and config mutations all produce FORBIDDEN impact."""
    guard = _guard()
    forbidden = {
        "rm -rf /": "non_git_binary",
        "git -c core.pager=calc status": "blocked_global_option:-c",
        "git --exec-path=/tmp log": "blocked_global_option:--exec-path=/tmp",
        "git --config-env=core.pager=X log": "blocked_global_option:--config-env=core.pager=x",
        "git config core.pager calc": "configuration_mutation",
        "git -p status": "pager_injection",
        "git push origin $(echo main)": "process_substitution",
    }
    for cmd, expected_reason in forbidden.items():
        t = guard.classify_transition(cmd)
        assert t.impact == TransitionImpact.FORBIDDEN, cmd
        assert t.admissible is False, cmd
        assert t.reason == expected_reason, f"{cmd!r}: got {t.reason!r}, want {expected_reason!r}"


def test_classify_transition_subcommand_is_populated():
    """The subcommand field must be set so audit logs have a named operation."""
    guard = _guard()
    assert guard.classify_transition("git log --oneline").subcommand == "log"
    assert guard.classify_transition("git reset --hard HEAD").subcommand == "reset"
    assert guard.classify_transition("git push origin x").subcommand == "push"
    assert guard.classify_transition("git rebase main").subcommand == "rebase"


def test_classify_transition_reason_is_machine_readable():
    """Reason tokens must be non-empty strings with no whitespace (audit-log safe)."""
    guard = _guard()
    for cmd in ("git log", "git reset --hard", "git push --force",
                "git rebase", "git config x y", "rm -rf /"):
        t = guard.classify_transition(cmd)
        assert t.reason, f"empty reason for {cmd!r}"
        assert " " not in t.reason.split(":")[0], \
            f"reason prefix has whitespace for {cmd!r}: {t.reason!r}"
