from tas_pythonetics.git_safety import GitActionGuard, GitStateMonitor
monitor = GitStateMonitor()
guard = GitActionGuard(monitor)
# Is git checkout -c allowed?
print("Is valid:", guard.authorize_command("git checkout -c mybranch"))
