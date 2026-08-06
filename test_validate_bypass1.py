from codex_tas_runner import validate_script
# Can we bypass environment variable execution by passing them to env?
print(validate_script("env VAR=pwned ls"))
# Can we bypass bash -c by attaching it?
print(validate_script("bash -c'echo pwned'"))
# Can we bypass by setting an environment variable before the command?
print(validate_script("VAR=pwned ls"))
