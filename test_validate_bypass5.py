from codex_tas_runner import validate_script
# This should be blocked if we can use it to execute arbitrary commands
print(validate_script("PYTHONPATH=pwned python3 test_codex_env.py"))
