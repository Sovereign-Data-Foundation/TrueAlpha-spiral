with open("codex_tas_runner.py", "r") as f:
    content = f.read()

# Replace block where we check for variable assignments
search = """        cmd_tokens = []
        for token in tokens:
            if token in (';', '&&', '||', '|', '&'):
                if cmd_tokens:
                    cmd_name = cmd_tokens[0]
                    if '=' in cmd_name:
                        parts = cmd_name.split('=', 1)
                        if len(cmd_tokens) > 1:
                            cmd_name = cmd_tokens[1]
                        else:
                            cmd_name = None"""

replace = """        cmd_tokens = []
        for token in tokens:
            if token in (';', '&&', '||', '|', '&'):
                if cmd_tokens:
                    cmd_idx = 0
                    while cmd_idx < len(cmd_tokens) and '=' in cmd_tokens[cmd_idx]:
                        cmd_idx += 1

                    if cmd_idx < len(cmd_tokens):
                        cmd_name = cmd_tokens[cmd_idx]
                        cmd_args = cmd_tokens[cmd_idx+1:]
                    else:
                        cmd_name = None
                        cmd_args = []"""

content = content.replace(search, replace, 1)


search2 = """                    if cmd_name and cmd_name not in ALLOWED_COMMANDS and cmd_name not in POSIX_KEYWORDS:
                        if not (cmd_name.startswith('./') or cmd_name.startswith('/')):
                            return False, f"Unauthorized command: {cmd_name}"
                        else:
                            return False, "Unauthorized path-based execution"
                    if cmd_name in ('bash', 'python', 'python3'):
                        for token_arg in cmd_tokens[1:]:"""

replace2 = """                    if cmd_name and cmd_name not in ALLOWED_COMMANDS and cmd_name not in POSIX_KEYWORDS:
                        if not (cmd_name.startswith('./') or cmd_name.startswith('/')):
                            return False, f"Unauthorized command: {cmd_name}"
                        else:
                            return False, "Unauthorized path-based execution"
                    if cmd_name in ('bash', 'python', 'python3'):
                        for token_arg in cmd_args:"""

content = content.replace(search2, replace2, 1)

search3 = """        if cmd_tokens:
            cmd_name = cmd_tokens[0]
            if '=' in cmd_name:
                parts = cmd_name.split('=', 1)
                if len(cmd_tokens) > 1:
                    cmd_name = cmd_tokens[1]
                else:
                    cmd_name = None"""
replace3 = """        if cmd_tokens:
            cmd_idx = 0
            while cmd_idx < len(cmd_tokens) and '=' in cmd_tokens[cmd_idx]:
                cmd_idx += 1

            if cmd_idx < len(cmd_tokens):
                cmd_name = cmd_tokens[cmd_idx]
                cmd_args = cmd_tokens[cmd_idx+1:]
            else:
                cmd_name = None
                cmd_args = []"""
content = content.replace(search3, replace3, 1)

search4 = """            if cmd_name and cmd_name not in ALLOWED_COMMANDS and cmd_name not in POSIX_KEYWORDS:
                if not (cmd_name.startswith('./') or cmd_name.startswith('/')):
                    return False, f"Unauthorized command: {cmd_name}"
                else:
                    return False, "Unauthorized path-based execution"
            if cmd_name in ('bash', 'python', 'python3'):
                for token_arg in cmd_tokens[1:]:"""
replace4 = """            if cmd_name and cmd_name not in ALLOWED_COMMANDS and cmd_name not in POSIX_KEYWORDS:
                if not (cmd_name.startswith('./') or cmd_name.startswith('/')):
                    return False, f"Unauthorized command: {cmd_name}"
                else:
                    return False, "Unauthorized path-based execution"
            if cmd_name in ('bash', 'python', 'python3'):
                for token_arg in cmd_args:"""
content = content.replace(search4, replace4, 1)

with open("codex_tas_runner.py", "w") as f:
    f.write(content)
