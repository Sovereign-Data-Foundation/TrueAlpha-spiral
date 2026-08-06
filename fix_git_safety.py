with open("tas_pythonetics/src/tas_pythonetics/git_safety.py", "r") as f:
    content = f.read()

# Replace the first token check block
search = """        for token in lower_tokens:
            if token == "-c" or token.startswith("--exec-path") or token == "--paginate" or token.startswith("--config-env"):
                logger.warning(f"BLOCKED: Dangerous global option '{token}'")
                return False"""
replace = ""
content = content.replace(search, replace, 1)

# Modify subcommand index check
search = """            if tokens[i] in ("-C", "-c", "--work-tree", "--git-dir", "--namespace"):
                i += 2
            else:
                i += 1"""
replace = """            if tokens[i] in ("-C", "-c", "--work-tree", "--git-dir", "--namespace"):
                i += 2
            elif tokens[i].startswith("-c") and len(tokens[i]) > 2:
                i += 1
            else:
                i += 1"""
content = content.replace(search, replace, 1)

# Replace the -p global option check with all global options check
search = """        # Check for global -p option (before the subcommand)
        for i in range(1, len(tokens)):
            if tokens[i].lower() == "-p":
                if subcommand_idx == -1 or i < subcommand_idx:
                    logger.warning(f"BLOCKED: Dangerous global option '-p' '{command}'")
                    return False"""
replace = """        # Check for global dangerous options (before the subcommand)
        for i in range(1, len(tokens)):
            if subcommand_idx == -1 or i < subcommand_idx:
                token_lower = tokens[i].lower()
                if token_lower == "-c" or token_lower.startswith("-c") or token_lower.startswith("--exec-path") or token_lower in ("-p", "--paginate") or token_lower.startswith("--config-env"):
                    logger.warning(f"BLOCKED: Dangerous global option '{tokens[i]}' in '{command}'")
                    return False"""
content = content.replace(search, replace, 1)

with open("tas_pythonetics/src/tas_pythonetics/git_safety.py", "w") as f:
    f.write(content)
