from codex_tas_runner import validate_script
print(validate_script("VAR=pwned ls"))
print(validate_script("VAR=pwned malicious"))
print(validate_script("ENV1=val1 ENV2=val2 bash"))
print(validate_script("ENV1=val1 ENV2=val2 bash -c 'echo pwned'"))
print(validate_script("BASH_ENV=test_codex_env.py bash"))
