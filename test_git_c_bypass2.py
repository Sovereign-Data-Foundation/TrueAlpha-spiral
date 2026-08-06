import subprocess
try:
    subprocess.run(["git", "-ccore.pager=echo 'pwned'", "log"], capture_output=True, text=True, check=True)
except subprocess.CalledProcessError as e:
    print(e.stderr)
