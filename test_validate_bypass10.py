from codex_tas_runner import validate_script
# Can we string multiple env variables?
print(validate_script("ENV1=val1 ENV2=val2 bash"))
