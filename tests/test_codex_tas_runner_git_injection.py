import pytest
from codex_tas_runner import _check_command

def test_git_injection_blocked():
    assert _check_command(['git', 'clone', '--upload-pack=id']) == (False, 'Unauthorized git option: --upload-pack=id')
    assert _check_command(['git', 'clone', '-u', 'id']) == (False, 'Unauthorized git option: -u')
    assert _check_command(['git', 'clone', '-u=id']) == (False, 'Unauthorized git option: -u=id')
    assert _check_command(['git', 'fetch', '--receive-pack=evil']) == (False, 'Unauthorized git option: --receive-pack=evil')

def test_git_injection_blocked_advanced():
    assert _check_command(['git', 'clone', 'log', '-c', 'core.pager=!sh', 'http://a']) == (False, 'Unauthorized git option: -c')
    assert _check_command(['git', 'config', 'core.pager', '!sh']) == (False, 'Unauthorized git subcommand: config')
    assert _check_command(['git', 'clone', '-u', 'log']) == (False, 'Unauthorized git option: -u')

def test_git_normal_allowed():
    assert _check_command(['git', 'clone', 'https://github.com/truealphaspiral/tas_gpt.git']) == (True, '')
    assert _check_command(['git', 'log', '-c']) == (True, '')
    assert _check_command(['git', 'checkout', 'config']) == (True, '')
