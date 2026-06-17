## 2026-03-30 - [Command Injection via Inadequate Command Restriction]
**Vulnerability:** Command injection/arbitrary command execution in `tas_pythonetics/src/tas_pythonetics/git_safety.py`. `GitActionGuard.authorize_command` failed to verify that the command being checked actually started with "git".
**Learning:** Security guards designed to filter specific harmful arguments (like `rebase` or `--force`) must also strictly enforce the root command identity, otherwise they inadvertently allow entirely different executables to bypass the filters.
**Prevention:** Always validate the root command (the first token) against a strict allowlist before applying argument-specific filters when performing command execution filtering.

## 2026-06-17 - [Command Injection Bypass via Shell Operators]
**Vulnerability:** Command injection bypass in `tas_pythonetics/src/tas_pythonetics/git_safety.py`. `GitActionGuard.authorize_command` failed to check for shell operators (e.g., `|`, `&&`, `;`) outside of quotes or command substitution (e.g., `$()`, backticks).
**Learning:** Checking the first token (e.g., `"git"`) is insufficient if the string is later evaluated or if the parser does not split on unquoted shell operators.
**Prevention:** Use `shlex.shlex(posix=True, punctuation_chars=True)` to accurately extract shell operators and block them, and explicitly reject raw control characters (like `\n`) and command substitution primitives.
