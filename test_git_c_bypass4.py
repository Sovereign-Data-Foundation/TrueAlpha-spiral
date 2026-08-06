from tas_pythonetics.git_safety import GitActionGuard, GitStateMonitor
monitor = GitStateMonitor()
guard = GitActionGuard(monitor)
# Is git commit -m test allowed?
print("Is valid:", guard.authorize_command("git commit -m test"))
