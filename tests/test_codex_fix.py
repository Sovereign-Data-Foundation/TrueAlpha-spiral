import pytest
from codex_tas_runner import validate_script, get_codex_script, _split_operators


def test_valid_script():
    script = "echo 'hello world'\nls -la"
    is_valid, msg = validate_script(script)
    assert is_valid, msg


def test_unethical_script():
    script = "echo 'I will do harm'"
    is_valid, msg = validate_script(script)
    assert not is_valid
    assert "Unethical content detected" in msg


def test_subshell_blocked():
    script = "echo $(ls)"
    is_valid, msg = validate_script(script)
    assert not is_valid
    assert "Subshells are blocked" in msg

    script = "echo `ls`"
    is_valid, msg = validate_script(script)
    assert not is_valid
    assert "Subshells are blocked" in msg


def test_unauthorized_command():
    script = "wget http://example.com"
    is_valid, msg = validate_script(script)
    assert not is_valid
    assert "Unauthorized command" in msg


def test_path_based_execution():
    script = "./malicious.sh"
    is_valid, msg = validate_script(script)
    assert not is_valid
    assert "Unauthorized path-based execution" in msg

    script = "/usr/bin/wget http://example.com"
    is_valid, msg = validate_script(script)
    assert not is_valid
    assert "Unauthorized path-based execution" in msg


def test_operator_chaining():
    for script in (
        "echo 'hello' ; wget http://example.com",
        "echo 'hello' && wget http://example.com",
        "echo 'hello' || wget http://example.com",
    ):
        is_valid, msg = validate_script(script)
        assert not is_valid
        assert "Unauthorized command" in msg


def test_operator_chaining_no_whitespace():
    """P1 fix: operators attached without spaces must still be caught."""
    for script in (
        "echo ok;wget http://example.com",
        "echo ok&&wget http://example.com",
        "echo ok||wget http://example.com",
        "echo ok|wget http://example.com",
    ):
        is_valid, msg = validate_script(script)
        assert not is_valid
        assert "Unauthorized command" in msg


def test_get_codex_script_raises_when_openai_missing(monkeypatch):
    """P2 fix: missing OpenAI SDK must raise RuntimeError, not return ''."""
    import codex_tas_runner
    monkeypatch.setattr(codex_tas_runner, "openai", None)
    with pytest.raises(RuntimeError, match="OpenAI SDK"):
        get_codex_script()


def test_split_operators_embedded():
    """Unit tests for _split_operators helper."""
    assert _split_operators(["echo", "ok;wget", "x"]) == ["echo", "ok", ";", "wget", "x"]
    assert _split_operators(["echo", "ok&&wget", "x"]) == ["echo", "ok", "&&", "wget", "x"]
    assert _split_operators(["echo", "ok||wget", "x"]) == ["echo", "ok", "||", "wget", "x"]
    assert _split_operators(["echo", "ok|wget", "x"]) == ["echo", "ok", "|", "wget", "x"]


def test_split_operators_already_separated():
    """Tokens that are already separate should pass through unchanged."""
    assert _split_operators(["echo", "ok", ";", "ls"]) == ["echo", "ok", ";", "ls"]
    assert _split_operators(["echo", "hello"]) == ["echo", "hello"]


def test_split_operators_multiple_operators():
    """Multiple operators in a single token."""
    assert _split_operators(["a;b;c"]) == ["a", ";", "b", ";", "c"]


def test_operator_chaining_ampersand():
    for script in (
        "echo 'hello' & wget http://example.com",
        "echo ok&wget http://example.com",
    ):
        is_valid, msg = validate_script(script)
        assert not is_valid
        assert "Unauthorized command" in msg


def test_redirection_with_ampersand_allowed():
    script = "python tas_agent.py --task 'self-test' > audit.log 2>&1"
    is_valid, msg = validate_script(script)
    assert is_valid, msg

    script = "python tas_agent.py --task 'self-test' &> audit.log"
    is_valid, msg = validate_script(script)
    assert is_valid, msg


def test_multiple_inline_environment_assignments_fail_closed():
    for script in (
        "A=1 bash -c 'echo pwned'",
        "A=1 B=2 bash -c 'echo pwned'",
        "PATH=/tmp python tas_agent.py",
        "BASH_ENV=payload.sh bash safe.sh",
        "PYTHONPATH=/tmp python tas_agent.py",
        "LD_PRELOAD=/tmp/x.so python tas_agent.py",
        "GIT_CONFIG_COUNT=1 git log -1",
    ):
        is_valid, msg = validate_script(script)
        assert not is_valid
        assert "Inline environment assignment is blocked" in msg


def test_export_is_a_bounded_capability():
    for script in (
        "export PATH=/tmp",
        "export BASH_ENV=payload.sh",
        "export PYTHONPATH=/tmp",
        "export LD_PRELOAD=/tmp/x.so",
        "export GIT_CONFIG_COUNT=1",
    ):
        is_valid, msg = validate_script(script)
        assert not is_valid
        assert "Unauthorized environment variable" in msg

    for script in (
        "export SOURCE_DATE_EPOCH=0",
        "export PYTHONUNBUFFERED=1",
        "export PIP_DISABLE_PIP_VERSION_CHECK=1",
    ):
        is_valid, msg = validate_script(script)
        assert is_valid, msg


def test_source_is_restricted_to_virtualenv_activation():
    for script in (
        "source payload.sh",
        "source /tmp/payload.sh",
        "source ./setup.sh",
    ):
        is_valid, msg = validate_script(script)
        assert not is_valid
        assert "Unauthorized source target" in msg

    is_valid, msg = validate_script("source .venv/bin/activate")
    assert is_valid, msg


def test_interpreter_execution_flags_blocked_after_environment_hardening():
    for script in (
        "bash -c 'echo pwned'",
        "bash -lc 'echo pwned'",
        "python -c 'print(1)'",
        "python3 -m http.server",
    ):
        is_valid, msg = validate_script(script)
        assert not is_valid
        assert "Unauthorized execution option" in msg


def test_git_global_execution_options_blocked():
    for script in (
        "git -c core.pager='!sh -c id' log -1",
        "git -c=core.pager='!sh -c id' log -1",
        "git --config-env=core.pager=EVIL log -1",
        "git --exec-path=/tmp log -1",
        "git --ext-cmd=sh log -1",
        "git --config=core.pager='!id' log -1",
        "git config core.pager '!id'",
        "git --work-tree repo log -1",
        "git --git-dir repo/.git log -1",
    ):
        is_valid, msg = validate_script(script)
        assert not is_valid
        assert "Unauthorized" in msg


def test_git_safe_short_c_only_after_known_subcommand():
    for script in (
        "git log -c -1",
        "git grep -c needle",
        "git switch -c feature/test",
    ):
        is_valid, msg = validate_script(script)
        assert is_valid, msg

    is_valid, msg = validate_script("git log -c=core.pager=evil")
    assert not is_valid
    assert "Unauthorized git option" in msg


def test_git_value_bearing_global_option_does_not_become_subcommand():
    for script in (
        "git -C repo log -c -1",
        "git -Crepo grep -c needle",
        "git -C ./repo switch -c feature/test",
    ):
        is_valid, msg = validate_script(script)
        assert is_valid, msg


def test_git_context_path_is_bounded():
    for script in (
        "git -C /tmp log -1",
        "git -C ../repo log -1",
        "git -C repo/../../tmp log -1",
        "git -C '~/repo' log -1",
    ):
        is_valid, msg = validate_script(script)
        assert not is_valid
        assert "git -C path" in msg


def test_git_subcommand_cannot_inherit_global_config_semantics():
    is_valid, msg = validate_script("git -C repo clone -c core.pager=evil origin")
    assert not is_valid
    assert "Unauthorized git option '-c' for clone" in msg
