from codex_tas_runner import validate_script
# This should be blocked if we can use it to execute arbitrary commands
print(validate_script("BASH_ENV=pwned bash -c 'echo done'"))
print(validate_script("PYTHONSTARTUP=pwned python"))
