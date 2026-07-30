import enum
import logging
import subprocess
import shlex
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TransitionImpact(enum.Enum):
    """
    Characterizes what a Git operation will do to repository state.

    This is the S_candidate classification in the state-transition model:
        S_current + Action → S_candidate → Admissible(S_candidate)

    The guard evaluates the impact class of a proposed command before
    allowing any mutation.  Capability (the ability to run a command) is
    explicitly separated from authority (the right to cause its consequence).
    """
    READ_ONLY = "read_only"
    """No state mutation — inspection only (log, status, diff, show, fetch)."""
    LOCAL_SAFE = "local_safe"
    """Local, reversible state change (add, commit, checkout, stash, merge)."""
    LOCAL_DESTRUCTIVE = "local_destructive"
    """Local change with irreversible history impact (reset --hard, clean)."""
    LINEAGE_REWRITE = "lineage_rewrite"
    """Rewrites commit graph — destroys provenance (rebase, commit --amend)."""
    REMOTE_MUTATION = "remote_mutation"
    """Pushes new commits to a remote; requires branch authorization."""
    REMOTE_DESTRUCTIVE = "remote_destructive"
    """Rewrites or deletes remote history (force push, +refspec, --delete)."""
    FORBIDDEN = "forbidden"
    """Pre-authorized refusal: config injection, non-git binary, malformed input."""


@dataclass(frozen=True)
class StateTransition:
    """
    The explicit representation of a proposed Git state transition.

    subcommand — the Git subcommand that would execute (empty string if
                 the command cannot be parsed to that level)
    impact     — the consequence class; what the command would do to state
    admissible — whether the guard permits this transition
    reason     — machine-readable token explaining the decision, suitable
                 for audit logs and rule-provenance chains
    """
    subcommand: str
    impact: TransitionImpact
    admissible: bool
    reason: str

class GitStateMonitor:
    """
    Monitors the state of a Git repository to ensure it adheres to safety invariants.
    """
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path

    def get_current_branch(self) -> str:
        try:
            # Check for current branch name
            result = subprocess.run(
                ["git", "symbolic-ref", "--short", "HEAD"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            # Check for detached HEAD
            return "DETACHED_HEAD"

    def is_clean_state(self) -> bool:
        """
        Check if the working directory is clean.
        """
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            return not result.stdout.strip()
        except subprocess.CalledProcessError:
            return False

    def check_invariant(self, invariant_type: str) -> bool:
        """
        Check specific safety invariants.
        """
        if invariant_type == "NO_DETACHED_HEAD":
            return self.get_current_branch() != "DETACHED_HEAD"

        if invariant_type == "CLEAN_WORKING_DIR":
            return self.is_clean_state()

        return False

class GitActionGuard:
    """
    Intercepts and validates Git commands before execution.

    The invariants below are the root of trust for this guard.  They must
    remain auditable and change-controlled: any modification to
    _BLOCKED_GLOBAL_EXACT or _BLOCKED_GLOBAL_PREFIXES removes a security
    boundary and must be reviewed.  Call verify_own_integrity() to assert
    these invariants are intact at runtime.
    """
    PROTECTED_BRANCHES = frozenset(["main", "master", "production"])

    # Global options that are blocked unconditionally (exact match, lowercased).
    _BLOCKED_GLOBAL_EXACT: frozenset[str] = frozenset({"-c", "--paginate"})

    # Global options that are blocked by prefix (lowercased).  Any token
    # starting with one of these strings is refused.
    _BLOCKED_GLOBAL_PREFIXES: tuple[str, ...] = ("--exec-path", "--config-env")

    # Global options that consume the next token as their value.  Used to
    # advance the subcommand-index search past value arguments.
    _GLOBAL_VALUE_OPTIONS: frozenset[str] = frozenset(
        {"-C", "-c", "--work-tree", "--git-dir", "--namespace", "--config-env"}
    )

    def __init__(self, monitor: GitStateMonitor):
        self.monitor = monitor

    @classmethod
    def verify_own_integrity(cls) -> None:
        """Assert that the guard's critical invariants are intact.

        This method embodies the principle that integrity controls itself:
        the enforcement mechanism verifies its own rule set before being
        used.  It raises AssertionError if any invariant has been removed.
        """
        assert "-c" in cls._BLOCKED_GLOBAL_EXACT, \
            "INTEGRITY FAILURE: '-c' must be blocked"
        assert "--paginate" in cls._BLOCKED_GLOBAL_EXACT, \
            "INTEGRITY FAILURE: '--paginate' must be blocked"
        assert any(p == "--exec-path" for p in cls._BLOCKED_GLOBAL_PREFIXES), \
            "INTEGRITY FAILURE: '--exec-path' prefix must be blocked"
        assert any(p == "--config-env" for p in cls._BLOCKED_GLOBAL_PREFIXES), \
            "INTEGRITY FAILURE: '--config-env' prefix must be blocked"
        assert "--config-env" in cls._GLOBAL_VALUE_OPTIONS, \
            "INTEGRITY FAILURE: '--config-env' must be listed as a value-consuming option"
        assert isinstance(cls.PROTECTED_BRANCHES, frozenset), \
            "INTEGRITY FAILURE: PROTECTED_BRANCHES must be immutable"

    def classify_transition(self, command: str) -> StateTransition:
        """
        Map a proposed command to its explicit StateTransition.

        This is the core of the state-transition boundary:
            S_current + Action → S_candidate

        The returned StateTransition characterizes what the command would do
        to repository state (impact) and whether the guard permits it
        (admissible), along with a machine-readable reason token.

        All decisions are made before any mutation occurs.  The caller need
        only inspect transition.admissible to decide whether to proceed.
        """
        def refused(subcommand: str, impact: TransitionImpact, reason: str) -> StateTransition:
            return StateTransition(subcommand, impact, False, reason)

        def admitted(subcommand: str, impact: TransitionImpact, reason: str) -> StateTransition:
            return StateTransition(subcommand, impact, True, reason)

        # --- Pre-parse: structural injection attempts ---
        if any(marker in command for marker in ('<(', '>(', '$(', chr(96))):
            return refused("", TransitionImpact.FORBIDDEN, "process_substitution")

        try:
            tokens = shlex.split(command)
        except ValueError:
            return refused("", TransitionImpact.FORBIDDEN, "malformed_command")

        if not tokens:
            return refused("", TransitionImpact.FORBIDDEN, "empty_command")

        if tokens[0].lower() not in ("git", "git.exe"):
            return refused("", TransitionImpact.FORBIDDEN, "non_git_binary")

        lower_tokens = {t.lower() for t in tokens}

        # --- Blocked global options (config/exec injection surface) ---
        for token in lower_tokens:
            if (
                token in self._BLOCKED_GLOBAL_EXACT
                or any(token.startswith(p) for p in self._BLOCKED_GLOBAL_PREFIXES)
            ):
                return refused("", TransitionImpact.FORBIDDEN, f"blocked_global_option:{token}")

        # --- Locate subcommand ---
        subcommand_idx = -1
        i = 1
        while i < len(tokens):
            if not tokens[i].startswith("-"):
                subcommand_idx = i
                break
            if tokens[i] in self._GLOBAL_VALUE_OPTIONS:
                i += 2
            else:
                i += 1

        subcommand = tokens[subcommand_idx].lower() if subcommand_idx != -1 else ""

        # --- Subcommand-level forbidden operations ---
        if subcommand == "config":
            return refused(subcommand, TransitionImpact.FORBIDDEN, "configuration_mutation")

        # Global -p before the subcommand is a pager-injection vector
        for j in range(1, len(tokens)):
            if tokens[j].lower() == "-p":
                if subcommand_idx == -1 or j < subcommand_idx:
                    return refused(subcommand, TransitionImpact.FORBIDDEN, "pager_injection")

        # --- Lineage-rewriting operations ---
        if subcommand == "rebase":
            return refused(subcommand, TransitionImpact.LINEAGE_REWRITE, "lineage_rewrite_prohibited")

        if subcommand == "commit" and "--amend" in lower_tokens:
            return refused(subcommand, TransitionImpact.LINEAGE_REWRITE, "lineage_rewrite_prohibited")

        # --- Local destructive operations ---
        if subcommand == "reset" and "--hard" in lower_tokens:
            return refused(subcommand, TransitionImpact.LOCAL_DESTRUCTIVE, "local_destructive_prohibited")

        if subcommand == "clean":
            return refused(subcommand, TransitionImpact.LOCAL_DESTRUCTIVE, "local_destructive_prohibited")

        # --- Remote operations ---
        if subcommand == "push":
            for token in lower_tokens:
                if token == "-f" or token.startswith("--force") or token.startswith("--delete"):
                    return refused(subcommand, TransitionImpact.REMOTE_DESTRUCTIVE, "remote_destructive_prohibited")
            for token in tokens:
                if token.startswith("+"):
                    return refused(subcommand, TransitionImpact.REMOTE_DESTRUCTIVE, "remote_destructive_prohibited")
            try:
                current_branch = self.monitor.get_current_branch()
            except Exception:
                return refused(subcommand, TransitionImpact.REMOTE_MUTATION, "branch_state_unresolvable")
            if current_branch in self.PROTECTED_BRANCHES:
                return refused(subcommand, TransitionImpact.REMOTE_MUTATION, f"protected_branch:{current_branch}")
            return admitted(subcommand, TransitionImpact.REMOTE_MUTATION, "remote_mutation_admitted")

        # --- Read-only operations ---
        _READ_ONLY = frozenset({
            "log", "status", "diff", "show", "ls-files", "ls-tree", "cat-file",
            "rev-parse", "describe", "shortlog", "blame", "grep", "fetch",
        })
        if subcommand in _READ_ONLY:
            return admitted(subcommand, TransitionImpact.READ_ONLY, "read_only_admitted")

        # --- Local safe operations (local, reversible) ---
        return admitted(subcommand, TransitionImpact.LOCAL_SAFE, "local_safe_admitted")

    def authorize_command(self, command: str) -> bool:
        """
        Check if a command is safe to execute given the current state.

        Delegates to classify_transition to obtain the explicit
        S_current + Action → S_candidate evaluation, then returns
        whether the resulting transition is admissible.  Callers that
        need the full decision record should call classify_transition
        directly.
        """
        transition = self.classify_transition(command)
        if not transition.admissible:
            logger.warning(
                f"BLOCKED: subcommand={transition.subcommand!r} "
                f"impact={transition.impact.value} reason={transition.reason} "
                f"command={command!r}"
            )
        return transition.admissible

    def execute_safe(self, command: list) -> bool:
        """
        Execute a git command only if authorized.
        """
        cmd_str = " ".join(command)
        if self.authorize_command(cmd_str):
            try:
                subprocess.run(command, cwd=self.monitor.repo_path, check=True)
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"Command failed: {e}")
                return False
        return False
