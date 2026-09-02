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

def validate_script(script):
    if not TAS_Heartproof(script):
        return False, "Unethical content detected"

    if '$(' in script or '`' in script:
        return False, "Subshells are blocked"

    if '<(' in script or '>(' in script or '<<<' in script:
        return False, "Process substitution is blocked"

    def check_command(cmd_tokens):
        if not cmd_tokens:
            return True, "Valid"

        cmd_index = 0
        while cmd_index < len(cmd_tokens) and re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*=', cmd_tokens[cmd_index]):
            cmd_index += 1

        if cmd_index >= len(cmd_tokens):
            return True, "Valid"

        cmd_name = cmd_tokens[cmd_index]
        if cmd_name not in ALLOWED_COMMANDS and cmd_name not in POSIX_KEYWORDS:
            if not (cmd_name.startswith('./') or cmd_name.startswith('/')):
                return False, f"Unauthorized command: {cmd_name}"
            else:
                return False, "Unauthorized path-based execution"

        if cmd_name in ('bash', 'python', 'python3'):
            for token_arg in cmd_tokens[cmd_index+1:]:
                if token_arg in ('-c', '-m'):
                    return False, f"Unauthorized execution option '{token_arg}' for {cmd_name}"
                if token_arg.startswith('-') and not token_arg.startswith('--'):
                    if 'c' in token_arg or 'm' in token_arg:
                        return False, f"Unauthorized execution option '{token_arg}' for {cmd_name}"

        if cmd_name == 'git':
            safe_subcommands = {'switch', 'checkout', 'commit', 'log', 'grep'}
            seen_subcommand = None
            blocked_globals = ('--ext-cmd', '--exec-path', '--config', '--config-env', '--paginate')

            for token_arg in cmd_tokens[cmd_index+1:]:
                if not token_arg.startswith('-') and seen_subcommand is None:
                    seen_subcommand = token_arg

                for bg in blocked_globals:
                    if token_arg == bg or token_arg.startswith(bg + '='):
                        return False, f"Unauthorized git option '{token_arg}'"

                if token_arg == '-c' or token_arg.startswith('-c='):
                    if seen_subcommand not in safe_subcommands:
                        return False, f"Unauthorized git global option '{token_arg}'"

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
