from codex_tas_runner import validate_script
# Can we use BASH_ENV?
print(validate_script("BASH_ENV=pwned bash"))
