import shlex
print(shlex.split("ENV=pwned ls"))
print(shlex.split("ENV=pwned ls=foo"))
