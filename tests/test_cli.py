import pytest

from detective.cli import COMMANDS, main


@pytest.mark.parametrize("command", COMMANDS)
def test_stage_command_reports_stub(
    command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([command]) == 0
    assert capsys.readouterr().out == f"{command} is not implemented yet.\n"


def test_cli_requires_a_subcommand() -> None:
    with pytest.raises(SystemExit, match="2"):
        main([])
