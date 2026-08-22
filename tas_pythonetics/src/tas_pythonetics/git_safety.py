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

        # Locate the subcommand index
        subcommand_idx = -1
        i = 1
        while i < len(tokens):
            if not tokens[i].startswith("-"):
                subcommand_idx = i
                break
            # Skip argument for some common global options that take a value
            if tokens[i] in ("-C", "-c", "--work-tree", "--git-dir", "--namespace"):
                i += 2
            else:
                i += 1

        subcommand = tokens[subcommand_idx].lower() if subcommand_idx != -1 else ""

        # Check for dangerous options. Note: we need to handle '-c' and '-p' carefully
        # so we don't break valid commands like 'git switch -c new_branch' or 'git commit -p'
        for i in range(1, len(tokens)):
            token = tokens[i]

            # Global options that should NEVER appear (like --exec-path, --config-env, --ext-cmd)
            if (token.startswith("--config-env") or
                token.startswith("--exec-path") or
                token.startswith("--ext-cmd")):
                logger.warning(f"BLOCKED: Dangerous option '{token}'")
                return False

            # '--config' can be used safely in some contexts, but not as a global arg for clone
            if token.startswith("--config"):
                logger.warning(f"BLOCKED: Dangerous option '{token}'")
                return False

            # '-c' is a valid argument for 'switch', 'checkout', 'commit', etc.
            # but is DANGEROUS as a global option (config injection).
            # We must be careful not to block valid flags like --cached or --continue
            if token == "-c" or token.startswith("-c=") or token.startswith("-c"):
                # Make sure we only catch -c and its immediate concatenated values
                # (e.g. -ccore.pager=...) and NOT --cached.
                if not token.startswith("--") and (token == "-c" or token.startswith("-c")):
                    # If it's a global option (before subcommand), it's always blocked
                    if i < subcommand_idx or subcommand_idx == -1:
                        logger.warning(f"BLOCKED: Dangerous global option '{token}'")
                        return False

                    # If it's after the subcommand, it's safe for certain commands
                    if subcommand not in ("switch", "checkout", "commit", "submodule"):
                        logger.warning(f"BLOCKED: Dangerous option '{token}' for subcommand '{subcommand}'")
                        return False

            # '-p' or '--paginate'
            if token == "--paginate" or (not token.startswith("--") and token.lower().startswith("-p")):
                # Always blocked as global option
                if i < subcommand_idx or subcommand_idx == -1:
                     logger.warning(f"BLOCKED: Dangerous global option '{token}'")
                     return False

                # Allowed for these subcommands
                if subcommand not in ("log", "diff", "show", "add", "commit", "checkout", "reset", "stash"):
                    logger.warning(f"BLOCKED: Dangerous pagination option '{token}' for subcommand '{subcommand}'")
                    return False

        if subcommand_idx != -1 and tokens[subcommand_idx].lower() == "config":
            logger.warning(f"BLOCKED: git config is not allowed '{command}'")
            return False

        # Normalize tokens to lowercase for checking commands/flags
        lower_tokens = {t.lower() for t in tokens}

        # Check for remote execution injection
        for token in tokens:
            if token.startswith("--upload-pack") or token.startswith("--receive-pack"):
                logger.warning(f"BLOCKED: Remote pack execution is not allowed '{command}'")
                return False

        if subcommand_idx != -1 and tokens[subcommand_idx].lower() == "clone":
            if any(t.startswith("-u") for t in tokens):
                logger.warning(f"BLOCKED: Remote pack execution via -u is not allowed for clone '{command}'")
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
