## 2026-03-30 - [Command Injection via Inadequate Command Restriction]
**Vulnerability:** Command injection/arbitrary command execution in `tas_pythonetics/src/tas_pythonetics/git_safety.py`. `GitActionGuard.authorize_command` failed to verify that the command being checked actually started with "git".
**Learning:** Security guards designed to filter specific harmful arguments (like `rebase` or `--force`) must also strictly enforce the root command identity, otherwise they inadvertently allow entirely different executables to bypass the filters.
**Prevention:** Always validate the root command (the first token) against a strict allowlist before applying argument-specific filters when performing command execution filtering.

## 2026-03-30 - [Command Injection via Git Global Options]
**Vulnerability:** Arbitrary command execution in `tas_pythonetics/src/tas_pythonetics/git_safety.py`. `GitActionGuard.authorize_command` failed to block global configuration options like `-c core.pager=...` or `--exec-path=...`, allowing command execution via Git even when root commands and destructive arguments were checked.
**Learning:** Checking for subcommands (like `rebase`) and harmful arguments (like `--force`) is insufficient if the underlying executable (Git) supports configuration injection that overrides executable paths or specifies arbitrary executables for standard operations.
**Prevention:** Explicitly block configuration-modifying arguments and paths (like `-c`, `--exec-path`, `--paginate`) when wrapping extensible command-line tools.
