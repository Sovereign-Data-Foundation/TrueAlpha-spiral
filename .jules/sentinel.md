## 2026-03-30 - [Command Injection via Inadequate Command Restriction]
**Vulnerability:** Command injection/arbitrary command execution in `tas_pythonetics/src/tas_pythonetics/git_safety.py`. `GitActionGuard.authorize_command` failed to verify that the command being checked actually started with "git".
**Learning:** Security guards designed to filter specific harmful arguments (like `rebase` or `--force`) must also strictly enforce the root command identity, otherwise they inadvertently allow entirely different executables to bypass the filters.
**Prevention:** Always validate the root command (the first token) against a strict allowlist before applying argument-specific filters when performing command execution filtering.

## 2026-03-30 - [Command Injection via Git Global Options]
**Vulnerability:** Arbitrary command execution in `tas_pythonetics/src/tas_pythonetics/git_safety.py`. `GitActionGuard.authorize_command` failed to block global configuration options like `-c core.pager=...` or `--exec-path=...`, allowing command execution via Git even when root commands and destructive arguments were checked.
**Learning:** Checking for subcommands (like `rebase`) and harmful arguments (like `--force`) is insufficient if the underlying executable (Git) supports configuration injection that overrides executable paths or specifies arbitrary executables for standard operations.
**Prevention:** Explicitly block configuration-modifying arguments and paths (like `-c`, `--exec-path`, `--paginate`) when wrapping extensible command-line tools.

## 2026-03-31 - [Command Injection via Background Execution Operator]
**Vulnerability:** Command injection in `codex_tas_runner.py` via unhandled `&` bash operator. The script validator correctly tokenized and blocked malicious commands separated by `;`, `&&`, `||`, and `|`, but failed to include `&` in the list of command separators, allowing unauthorized commands to bypass the check when executed in the background (e.g., `echo ok & wget http://example.com`).
**Learning:** When validating bash or POSIX shell commands through tokenization, all control operators that separate commands must be strictly accounted for, including background execution (`&`), not just sequential or logical execution.
**Prevention:** Ensure the regular expression and tokenizer logic that split commands identify and handle all shell control operators, specifically `&`, alongside `;`, `&&`, `||`, and `|`.

## 2024-07-17 - [Process Substitution Command Injection Bypass]
**Vulnerability:** Command injection by process substitution `<(...)` and `>(...)` bypassed the command allowlist because `shlex.split` does not correctly tokenize them as commands.
**Learning:** `shlex.split` is insufficient to prevent advanced bash syntax like process substitution from executing arbitrary commands.
**Prevention:** Explicitly reject process substitution syntax `<(` and `>(` before tokenizing with `shlex`.
## 2026-03-31 - [Process Substitution Command Injection Bypass]
**Vulnerability:** Command injection by process substitution `<(...)` and `>(...)` bypassed the command allowlist because `shlex.split` does not correctly tokenize them as commands.
**Learning:** `shlex.split` is insufficient to prevent advanced bash syntax like process substitution from executing arbitrary commands.
**Prevention:** Explicitly reject process substitution syntax `<(` and `>(` before tokenizing with `shlex`.

## 2024-07-24 - Prevent Git Command Injection via `git config` and global options
**Vulnerability:** The Git wrapper allowed users to set arbitrary `git config` options and use global options like `-p`, which could be exploited for command injection via malicious configurations (e.g. `core.pager`).
**Learning:** Checking for flags naively without considering subcommand position allows bypassing filters. Subcommand-specific arguments (like `git log -p`) can overlap with global arguments (like `git -p status`) if not tracked via their position.
**Prevention:** Iterating through the tokens to locate the subcommand index allows separating global configuration/options (which shouldn't be overridden interactively) from safe, localized parameters (e.g., specific `-p` or `--patch` uses).

## 2024-07-26 - [Command Injection via Git --config-env Global Option]
**Vulnerability:** Arbitrary command execution via Git `git_safety.py`. `GitActionGuard.authorize_command` failed to block the `--config-env` global option. Similar to `-c`, `--config-env` allows injecting arbitrary configuration values from the environment (e.g. `core.pager`), bypassing filters that protect against direct configuration modification.
**Learning:** Preventing direct configuration injection with `-c` or `git config` is insufficient if the executable also supports injecting configurations via environment variables tied to command-line flags.
**Prevention:** Explicitly block all flags that allow arbitrary configuration values to be set during command execution, including `--config-env`, to prevent indirect command injection via manipulated configurations.
