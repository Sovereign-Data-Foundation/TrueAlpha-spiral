import re
text = """        for token in lower_tokens:
            if token == "-c" or token.startswith("--exec-path") or token == "--paginate" or token.startswith("--config-env"):
                logger.warning(f"BLOCKED: Dangerous global option '{token}'")
                return False"""
fixed = """        for token in lower_tokens:
            if token == "-c" or token.startswith("-c") or token.startswith("--exec-path") or token == "--paginate" or token.startswith("--config-env"):
                logger.warning(f"BLOCKED: Dangerous global option '{token}'")
                return False"""
print(fixed)
