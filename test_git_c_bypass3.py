import subprocess
try:
    proc = subprocess.run(["git", "-c", "core.pager=echo 'pwned'", "log"], capture_output=True, text=True, check=True)
    print("SUCCESS")
except subprocess.CalledProcessError as e:
    print(e.stderr)
