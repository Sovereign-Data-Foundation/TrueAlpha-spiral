"""
Run this with:  python codex_tas_runner.py
It will feed a single system+user prompt into OpenAI Codex, receive a bash
script, execute it line-by-line, and print a summary JSON.
"""
import os, subprocess, json, hashlib, time, shlex, re
from tas_pythonetics.ethics import TAS_Heartproof

try:
    import openai
    openai.api_key = os.getenv("OPENAI_API_KEY")  # <-- export before run
except ImportError:
    openai = None

SYSTEM = """You are a reliable DevOps assistant. 
Produce a POSIX-compliant bash script that:
1. Clones https://github.com/truealphaspiral/tas_gpt.git if not present.
2. Creates a Python venv  (.venv)  and installs requirements.
3. Copies examples/config.safe_mode.yaml to config.yaml.
4. Creates ledger/  directory if missing.
5. Runs:  python tas_agent.py --task \"self-test\"
6. Captures the console output to audit.log.
7. Computes SHA-256 of audit.log and writes it to ledger/self_test.hash
"""

def get_codex_script():
    if openai is None:
        raise RuntimeError(
            "OpenAI SDK is not installed or failed to import. "
            "Install it with: pip install openai"
        )
    resp = openai.ChatCompletion.create(
        model="gpt-4o-code",  # or "gpt-4o"
        messages=[{"role":"system","content":SYSTEM}]
    )
    return resp.choices[0].message.content


def run_bash(script):
    with open("run.sh","w") as f:
        f.write(script)
    os.chmod("run.sh", 0o755)
    proc = subprocess.run(["bash","run.sh"],
                          capture_output=True, text=True)
    return proc

ALLOWED_COMMANDS = {
    'echo', 'ls', 'cd', 'python', 'python3', 'git', 'cat', 'grep', 'mkdir', 'touch',
    'rm', 'cp', 'mv', 'chmod', 'source', 'export', 'pip', 'pytest', 'bash', 'venv', 'virtualenv', 'test', '[', ']'
}

POSIX_KEYWORDS = {
    'if', 'then', 'else', 'elif', 'fi', 'while', 'for', 'in', 'do', 'done', 'case', 'esac', '!', '{', '}'
}

# Environment mutation is itself a capability. The generated script may only
# export variables whose semantics do not redirect code loading/execution.
SAFE_EXPORT_VARS = {
    'SOURCE_DATE_EPOCH',
    'PYTHONUNBUFFERED',
    'PIP_DISABLE_PIP_VERSION_CHECK',
}

SAFE_SOURCE_TARGETS = {
    '.venv/bin/activate',
    './.venv/bin/activate',
}

_ENV_ASSIGN_RE = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)=(.*)$')
_SAFE_ENV_VALUE_RE = re.compile(r'^[a-zA-Z0-9_./:@%+,-]*$')
_SAFE_GIT_CONTEXT_RE = re.compile(r'^[a-zA-Z0-9_.@%+,-]+(?:/[a-zA-Z0-9_.@%+,-]+)*$')
_OPERATOR_RE = re.compile(r'(&&|\|\||[;]|\||(?<![>&])&(?!>))')


def _split_operators(tokens):
    """Re-tokenize shlex tokens so embedded operators are separate tokens.

    For example ``["echo", "ok;wget", "x"]`` becomes
    ``["echo", "ok", ";", "wget", "x"]``.
    """
    result = []
    for token in tokens:
        parts = _OPERATOR_RE.split(token)
        for part in parts:
            if part:  # skip empty strings from split
                result.append(part)
    return result


def _safe_git_context_path(value):
    """Permit only bounded relative paths for Git's global ``-C`` option."""
    if not value or value.startswith('/') or not _SAFE_GIT_CONTEXT_RE.fullmatch(value):
        return False
    return all(part not in ('', '..') for part in value.split('/'))


def validate_script(script):
    if not TAS_Heartproof(script):
        return False, "Unethical content detected"

    if '$(' in script or '`' in script:
        return False, "Subshells are blocked"

    if '<(' in script or '>(' in script or '<<<' in script:
        return False, "Process substitution is blocked"

    def check_git(cmd_tokens):
        safe_short_c_subcommands = {'switch', 'checkout', 'commit', 'log', 'grep', 'diff', 'show'}
        blocked_globals = (
            '--ext-cmd', '--extcmd', '--exec-path', '--config', '--config-env',
            '--paginate', '--no-pager', '--git-dir', '--work-tree', '--namespace',
            '--super-prefix',
        )

        args = cmd_tokens[1:]
        index = 0
        subcommand = None

        # Parse the global-option region before identifying the subcommand.
        # Value-bearing options must consume their value so it cannot be
        # mistaken for the subcommand (e.g. ``git -C repo log -c``).
        while index < len(args):
            token = args[index]

            for blocked in blocked_globals:
                if token == blocked or token.startswith(blocked + '='):
                    return False, f"Unauthorized git option '{token}'"

            if token == '-c' or token.startswith('-c=') or (token.startswith('-c') and token != '-C'):
                return False, f"Unauthorized git global option '{token}'"

            if token == '-C':
                if index + 1 >= len(args):
                    return False, "Git -C requires a path"
                context_path = args[index + 1]
                if not _safe_git_context_path(context_path):
                    return False, f"Unsafe git -C path '{context_path}'"
                index += 2
                continue

            if token.startswith('-C') and token != '-C':
                context_path = token[2:]
                if not _safe_git_context_path(context_path):
                    return False, f"Unsafe git -C path '{context_path}'"
                index += 1
                continue

            if token == '--':
                index += 1
                if index >= len(args):
                    return False, "Missing git subcommand"
                subcommand = args[index]
                index += 1
                break

            if token.startswith('-'):
                # Unknown global options fail closed. Do not guess whether an
                # unmodeled option consumes the following token.
                return False, f"Unauthorized git global option '{token}'"

            subcommand = token
            index += 1
            break

        if subcommand is None:
            return False, "Missing git subcommand"
        if subcommand == 'config':
            return False, "Unauthorized subcommand 'config' for git"

        # Subcommand arguments are evaluated in subcommand context. Exact -c
        # is permitted only where Git defines a non-configuration meaning.
        for token_arg in args[index:]:
            for blocked in blocked_globals:
                if token_arg == blocked or token_arg.startswith(blocked + '='):
                    return False, f"Unauthorized git option '{token_arg}'"

            if token_arg == '-c':
                if subcommand not in safe_short_c_subcommands:
                    return False, f"Unauthorized git option '{token_arg}' for {subcommand}"
            elif token_arg.startswith('-c'):
                return False, f"Unauthorized git option '{token_arg}'"

        return True, "Valid"

    def check_command(cmd_tokens):
        if not cmd_tokens:
            return True, "Valid"

        # Do not silently skip VAR=value prefixes. Prefix assignments can alter
        # PATH, BASH_ENV, PYTHONPATH, LD_PRELOAD, GIT_CONFIG_* and other process
        # semantics before the allowlisted executable starts.
        prefix = _ENV_ASSIGN_RE.match(cmd_tokens[0])
        if prefix:
            return False, f"Inline environment assignment is blocked: {prefix.group(1)}"

        cmd_name = cmd_tokens[0]
        if cmd_name not in ALLOWED_COMMANDS and cmd_name not in POSIX_KEYWORDS:
            if not (cmd_name.startswith('./') or cmd_name.startswith('/')):
                return False, f"Unauthorized command: {cmd_name}"
            return False, "Unauthorized path-based execution"

        if cmd_name == 'export':
            if len(cmd_tokens) == 1:
                return False, "Bare export is blocked"
            for token_arg in cmd_tokens[1:]:
                match = _ENV_ASSIGN_RE.match(token_arg)
                if not match:
                    return False, f"Export must use NAME=value form: {token_arg}"
                name, value = match.groups()
                if name not in SAFE_EXPORT_VARS:
                    return False, f"Unauthorized environment variable: {name}"
                if not _SAFE_ENV_VALUE_RE.fullmatch(value):
                    return False, f"Unsafe environment value for {name}"

        if cmd_name == 'source':
            if len(cmd_tokens) != 2 or cmd_tokens[1] not in SAFE_SOURCE_TARGETS:
                return False, "Unauthorized source target"

        if cmd_name in ('bash', 'python', 'python3'):
            for token_arg in cmd_tokens[1:]:
                if token_arg in ('-c', '-m'):
                    return False, f"Unauthorized execution option '{token_arg}' for {cmd_name}"
                if token_arg.startswith('-') and not token_arg.startswith('--'):
                    if 'c' in token_arg or 'm' in token_arg:
                        return False, f"Unauthorized execution option '{token_arg}' for {cmd_name}"

        if cmd_name == 'git':
            return check_git(cmd_tokens)

        return True, "Valid"

    lines = script.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        try:
            tokens = shlex.split(line, comments=True)
        except ValueError as e:
            return False, f"Syntax error: {e}"

        if not tokens:
            continue

        tokens = _split_operators(tokens)

        # Simple tokenizer to split by operators like ;, &&, ||, |, &
        cmd_tokens = []
        for token in tokens:
            if token in (';', '&&', '||', '|', '&'):
                if cmd_tokens:
                    is_valid, reason = check_command(cmd_tokens)
                    if not is_valid:
                        return False, reason
                cmd_tokens = []
            else:
                cmd_tokens.append(token)

        if cmd_tokens:
            is_valid, reason = check_command(cmd_tokens)
            if not is_valid:
                return False, reason

    print("Generated Script:\n")
    print(script)
    print("\n")

    # In a testing environment where stdin is not a tty, we can bypass or default.
    # But usually, user confirmation is required.
    if os.isatty(0):
        confirm = input("Execute this script? (y/N): ")
        if confirm.lower() != 'y':
            return False, "User rejected script execution"

    return True, "Valid"


if __name__ == "__main__":
    bash_script = get_codex_script()

    is_valid, reason = validate_script(bash_script)
    if not is_valid:
        print(f"Script validation failed: {reason}")
        exit(1)

    result = run_bash(bash_script)

    # compute final hash of audit.log if exists
    hash_val = ""
    if os.path.exists("ledger/self_test.hash"):
        with open("ledger/self_test.hash","rb") as f:
            hash_val = f.read().decode().strip()

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "returncode": result.returncode,
        "stdout_tail": result.stdout.splitlines()[-10:],
        "stderr_tail": result.stderr.splitlines()[-10:],
        "audit_hash": hash_val
    }

    print(json.dumps(report, indent=2))
# Nonce: 31330