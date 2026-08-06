from tas_pythonetics.git_safety import GitActionGuard, GitStateMonitor
monitor = GitStateMonitor()
guard = GitActionGuard(monitor)
# Is git commit -a -m allowed?
print("Is valid:", guard.authorize_command("git commit -a -m test"))
