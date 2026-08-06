from tas_pythonetics.git_safety import GitActionGuard, GitStateMonitor
monitor = GitStateMonitor()
guard = GitActionGuard(monitor)
# Is git commit -a -ccore.pager=pwned allowed?
print("Is valid:", guard.authorize_command("git commit -a -ccore.pager=pwned"))
