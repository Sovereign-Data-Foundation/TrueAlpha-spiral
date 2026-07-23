import logging
import subprocess
import shlex

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    """
    PROTECTED_BRANCHES = ["main", "master", "production"]

    def __init__(self, monitor: GitStateMonitor):
        self.monitor = monitor

    def authorize_command(self, command: str) -> bool:
        """
        Check if a command is safe to execute given the current state.
        Uses shlex to properly parse the command line.
        """
        if any(marker in command for marker in ('<(', '>(', '$(', chr(96))):
            logger.warning(f"BLOCKED: Process or command substitution syntax not allowed '{command}'")
            return False

        try:
            tokens = shlex.split(command)
        except ValueError:
            logger.warning(f"BLOCKED: Malformed command string '{command}'")
            return False

        if not tokens:
            return False

        if tokens[0].lower() not in ("git", "git.exe"):
            logger.warning(f"BLOCKED: Non-git command '{command}'")
            return False

        # Normalize tokens to lowercase for checking commands/flags
        # Keep a list instead of a set to preserve order for positional checks
        lower_tokens_list = [t.lower() for t in tokens]
        lower_tokens = set(lower_tokens_list)

        # Identify the subcommand to safely check it and global options.
        # We must skip over known global options that take arguments.
        subcmd_idx = -1
        skip_next = False
        for i, token in enumerate(lower_tokens_list[1:], start=1):
            if skip_next:
                skip_next = False
                continue

            # Global options taking an argument as a separate token
            if token in ("-c", "--exec-path", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--list-cmds", "--attr-source"):
                skip_next = True
                continue

            if not token.startswith("-"):
                subcmd_idx = i
                break

        # Check for global options before the subcommand
        global_options = lower_tokens_list[1:subcmd_idx] if subcmd_idx != -1 else lower_tokens_list[1:]

        # Block -p if it's used as a global option (--paginate alias)
        if "-p" in global_options:
            logger.warning(f"BLOCKED: Dangerous global option '-p'")
            return False

        # Block these options anywhere in the command
        for token in lower_tokens:
            if token == "-c" or token.startswith("--exec-path") or token == "--paginate":
                logger.warning(f"BLOCKED: Dangerous option '{token}'")
                return False

        # Block config subcommand
        if subcmd_idx != -1 and lower_tokens_list[subcmd_idx] == "config":
            logger.warning(f"BLOCKED: config command is not allowed '{command}'")
            return False

        # Check for rebase
        if "rebase" in lower_tokens:
            logger.warning(f"BLOCKED: Rebase is not allowed '{command}'")
            return False

        # Check for reset --hard
        if "reset" in lower_tokens and "--hard" in lower_tokens:
             logger.warning(f"BLOCKED: reset --hard is not allowed '{command}'")
             return False

        # Check for push operations
        if "push" in lower_tokens:
            # Check for force flags
            for token in lower_tokens:
                if token == "-f" or token.startswith("--force") or token.startswith("--delete"):
                    logger.warning(f"BLOCKED: Force/Delete push is not allowed '{command}'")
                    return False

            # Check for +refspec in original tokens (case sensitive for refspecs usually, but '+' is key)
            # We skip the first token usually ("git") and "push" command itself, but iterating all is safer.
            for token in tokens:
                # Refspecs starting with + are force pushes
                if token.startswith("+"):
                    logger.warning(f"BLOCKED: Force push via +refspec is not allowed '{command}'")
                    return False

            # Check for protected branch manipulation
            try:
                current_branch = self.monitor.get_current_branch()
            except Exception:
                # If we can't determine branch, fail safe
                return False

            if current_branch in self.PROTECTED_BRANCHES:
                 logger.warning(f"BLOCKED: Direct push to protected branch '{current_branch}'")
                 return False

        return True

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
