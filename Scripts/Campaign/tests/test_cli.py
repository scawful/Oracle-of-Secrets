"""Tests for campaign CLI module (__main__.py).

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D: CLI interface for campaign operations

These tests verify the command-line interface functionality
without requiring a live emulator connection.
"""

import pytest
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class TestCLIImport:
    """Test CLI module can be imported."""

    def test_import_main_module(self):
        """Test __main__ module imports successfully."""
        from scripts.campaign import __main__
        assert hasattr(__main__, 'main')
        assert hasattr(__main__, 'cmd_status')
        assert hasattr(__main__, 'cmd_test')
        assert hasattr(__main__, 'cmd_check')
        assert hasattr(__main__, 'cmd_run')
        assert hasattr(__main__, 'cmd_report')
        assert hasattr(__main__, 'cmd_commands')


class TestCommandsCommand:
    """Test the 'commands' command."""

    def test_cmd_commands_runs(self):
        """Test commands command executes without error."""
        from scripts.campaign.__main__ import cmd_commands

        args = Mock()
        args.json = False
        args.examples = False

        result = cmd_commands(args)
        assert result == 0

    def test_commands_output_format(self, capsys):
        """Test commands output has expected sections."""
        from scripts.campaign.__main__ import cmd_commands

        args = Mock()
        args.json = False
        args.examples = False

        cmd_commands(args)

        captured = capsys.readouterr()
        assert 'CAMPAIGN CLI COMMANDS' in captured.out
        assert 'Monitoring:' in captured.out
        assert 'Testing & Execution:' in captured.out
        assert 'Save States:' in captured.out
        assert 'Utility:' in captured.out

    def test_commands_with_examples(self, capsys):
        """Test commands output includes examples when requested."""
        from scripts.campaign.__main__ import cmd_commands

        args = Mock()
        args.json = False
        args.examples = True

        cmd_commands(args)

        captured = capsys.readouterr()
        assert 'EXAMPLES:' in captured.out
        assert 'python -m scripts.campaign' in captured.out

    def test_commands_json_output(self, capsys):
        """Test commands JSON output is valid."""
        import json
        from scripts.campaign.__main__ import cmd_commands

        args = Mock()
        args.json = True
        args.examples = False

        cmd_commands(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'commands' in data
        assert len(data['commands']) >= 14

    def test_commands_arg_parsing(self):
        """Test commands argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'commands']):
            with patch('scripts.campaign.__main__.cmd_commands') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.json is False
                assert args.examples is False

    def test_commands_command_executable(self):
        """Test commands command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'commands'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'CAMPAIGN CLI COMMANDS' in result.stdout


class TestMilestoneCommand:
    """Test the 'milestone' command."""

    def test_cmd_milestone_runs(self):
        """Test milestone command executes without error."""
        from scripts.campaign.__main__ import cmd_milestone

        args = Mock()
        args.json = False

        result = cmd_milestone(args)
        assert result == 0

    def test_milestone_output_format(self, capsys):
        """Test milestone output has expected sections."""
        from scripts.campaign.__main__ import cmd_milestone

        args = Mock()
        args.json = False

        cmd_milestone(args)

        captured = capsys.readouterr()
        # Should have progress info
        assert 'Current:' in captured.out or 'MILESTONE REACHED' in captured.out

    def test_milestone_json_output(self, capsys):
        """Test milestone JSON output is valid."""
        import json
        from scripts.campaign.__main__ import cmd_milestone

        args = Mock()
        args.json = True

        cmd_milestone(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'target' in data
        assert 'current' in data
        assert 'remaining' in data
        assert 'percent' in data
        assert 'reached' in data

    def test_milestone_json_structure(self, capsys):
        """Test milestone JSON has correct values."""
        import json
        from scripts.campaign.__main__ import cmd_milestone

        args = Mock()
        args.json = True

        cmd_milestone(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data['target'] == 100
        assert data['current'] >= 0
        assert data['percent'] >= 0
        assert isinstance(data['reached'], bool)

    def test_milestone_arg_parsing(self):
        """Test milestone argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'milestone']):
            with patch('scripts.campaign.__main__.cmd_milestone') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.json is False

    def test_milestone_command_executable(self):
        """Test milestone command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'milestone'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        # Should have either progress or milestone reached
        assert 'Current:' in result.stdout or 'MILESTONE' in result.stdout


class TestVersionCommand:
    """Test the 'version' command."""

    def test_cmd_version_runs(self):
        """Test version command executes without error."""
        from scripts.campaign.__main__ import cmd_version

        args = Mock()
        args.json = False

        result = cmd_version(args)
        assert result == 0

    def test_version_output_format(self, capsys):
        """Test version output has expected info."""
        from scripts.campaign.__main__ import cmd_version

        args = Mock()
        args.json = False

        cmd_version(args)

        captured = capsys.readouterr()
        assert 'Oracle of Secrets Campaign CLI' in captured.out
        assert 'Version' in captured.out
        assert 'Commands:' in captured.out
        assert 'Python:' in captured.out

    def test_version_json_output(self, capsys):
        """Test version JSON output is valid."""
        import json
        from scripts.campaign.__main__ import cmd_version

        args = Mock()
        args.json = True

        cmd_version(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'name' in data
        assert 'version' in data
        assert 'build_date' in data
        assert 'commands' in data
        assert 'python' in data

    def test_version_arg_parsing(self):
        """Test version argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'version']):
            with patch('scripts.campaign.__main__.cmd_version') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.json is False

    def test_version_command_executable(self):
        """Test version command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'version'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'Version' in result.stdout


class TestQuickstartCommand:
    """Test the 'quickstart' command."""

    def test_cmd_quickstart_runs(self):
        """Test quickstart command executes without error."""
        from scripts.campaign.__main__ import cmd_quickstart

        args = Mock()

        result = cmd_quickstart(args)
        assert result == 0

    def test_quickstart_output_format(self, capsys):
        """Test quickstart output has expected sections."""
        from scripts.campaign.__main__ import cmd_quickstart

        args = Mock()

        cmd_quickstart(args)

        captured = capsys.readouterr()
        assert 'QUICKSTART' in captured.out
        assert 'CHECK STATUS' in captured.out
        assert 'dashboard' in captured.out
        assert 'milestone' in captured.out
        assert 'history' in captured.out
        assert 'goals' in captured.out

    def test_quickstart_arg_parsing(self):
        """Test quickstart argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'quickstart']):
            with patch('scripts.campaign.__main__.cmd_quickstart') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                mock_cmd.assert_called_once()

    def test_quickstart_command_executable(self):
        """Test quickstart command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'quickstart'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'QUICKSTART' in result.stdout


class TestAgentsCommand:
    """Test the 'agents' command."""

    def test_cmd_agents_runs(self):
        """Test agents command executes without error."""
        from scripts.campaign.__main__ import cmd_agents

        args = Mock()
        args.json = False

        result = cmd_agents(args)
        assert result == 0

    def test_agents_output_format(self, capsys):
        """Test agents output has expected sections."""
        from scripts.campaign.__main__ import cmd_agents

        args = Mock()
        args.json = False

        cmd_agents(args)

        captured = capsys.readouterr()
        assert 'CAMPAIGN AGENTS' in captured.out
        assert 'Overseer' in captured.out
        assert 'Explorer' in captured.out
        assert 'Total Iterations' in captured.out

    def test_agents_json_output(self, capsys):
        """Test agents JSON output is valid."""
        import json
        from scripts.campaign.__main__ import cmd_agents

        args = Mock()
        args.json = True

        result = cmd_agents(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'agents' in data
        assert 'total_iterations' in data
        assert len(data['agents']) == 2

    def test_agents_arg_parsing(self):
        """Test agents argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'agents']):
            with patch('scripts.campaign.__main__.cmd_agents') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                mock_cmd.assert_called_once()

    def test_agents_command_executable(self):
        """Test agents command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'agents'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'CAMPAIGN AGENTS' in result.stdout


class TestConfigCommand:
    """Test the 'config' command."""

    def test_cmd_config_runs(self):
        """Test config command executes without error."""
        from scripts.campaign.__main__ import cmd_config

        args = Mock()
        args.json = False

        result = cmd_config(args)
        assert result == 0

    def test_config_output_format(self, capsys):
        """Test config output has expected sections."""
        from scripts.campaign.__main__ import cmd_config

        args = Mock()
        args.json = False

        cmd_config(args)

        captured = capsys.readouterr()
        assert 'CAMPAIGN CONFIGURATION' in captured.out
        assert 'Paths:' in captured.out
        assert 'Status:' in captured.out
        assert 'project_root' in captured.out.lower().replace(' ', '_')

    def test_config_json_output(self, capsys):
        """Test config JSON output is valid."""
        import json
        from scripts.campaign.__main__ import cmd_config

        args = Mock()
        args.json = True

        result = cmd_config(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'paths' in data
        assert 'existence' in data
        assert 'test_files' in data

    def test_config_arg_parsing(self):
        """Test config argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'config']):
            with patch('scripts.campaign.__main__.cmd_config') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                mock_cmd.assert_called_once()

    def test_config_command_executable(self):
        """Test config command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'config'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'CAMPAIGN CONFIGURATION' in result.stdout


class TestHealthCommand:
    """Test the 'health' command."""

    def test_cmd_health_runs(self):
        """Test health command executes without error."""
        from scripts.campaign.__main__ import cmd_health

        args = Mock()
        args.json = False

        result = cmd_health(args)
        assert result in [0, 1]  # Can return 0 (healthy) or 1 (unhealthy)

    def test_health_output_format(self, capsys):
        """Test health output has expected sections."""
        from scripts.campaign.__main__ import cmd_health

        args = Mock()
        args.json = False

        cmd_health(args)

        captured = capsys.readouterr()
        assert 'CAMPAIGN HEALTH CHECK' in captured.out
        assert 'Campaign Log' in captured.out
        assert 'Status:' in captured.out

    def test_health_json_output(self, capsys):
        """Test health JSON output is valid."""
        import json
        from scripts.campaign.__main__ import cmd_health

        args = Mock()
        args.json = True

        cmd_health(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'overall' in data
        assert 'checks' in data
        assert isinstance(data['checks'], list)

    def test_health_arg_parsing(self):
        """Test health argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'health']):
            with patch('scripts.campaign.__main__.cmd_health') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                mock_cmd.assert_called_once()

    def test_health_command_executable(self):
        """Test health command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'health'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'CAMPAIGN HEALTH CHECK' in result.stdout


class TestChangelogCommand:
    """Test the 'changelog' command."""

    def test_cmd_changelog_runs(self):
        """Test changelog command executes without error."""
        from scripts.campaign.__main__ import cmd_changelog

        args = Mock()
        args.json = False
        args.limit = None

        result = cmd_changelog(args)
        assert result == 0

    def test_changelog_output_format(self, capsys):
        """Test changelog output has expected sections."""
        from scripts.campaign.__main__ import cmd_changelog

        args = Mock()
        args.json = False
        args.limit = None

        cmd_changelog(args)

        captured = capsys.readouterr()
        assert 'CAMPAIGN CLI CHANGELOG' in captured.out
        assert 'Version' in captured.out
        assert 'Total:' in captured.out

    def test_changelog_json_output(self, capsys):
        """Test changelog JSON output is valid."""
        import json
        from scripts.campaign.__main__ import cmd_changelog

        args = Mock()
        args.json = True
        args.limit = None

        result = cmd_changelog(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'changelog' in data
        assert 'total_changes' in data

    def test_changelog_limit(self, capsys):
        """Test changelog limit parameter."""
        from scripts.campaign.__main__ import cmd_changelog

        args = Mock()
        args.json = False
        args.limit = 3

        cmd_changelog(args)

        captured = capsys.readouterr()
        assert '... and' in captured.out  # Should show truncation message

    def test_changelog_command_executable(self):
        """Test changelog command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'changelog'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'CAMPAIGN CLI CHANGELOG' in result.stdout


class TestAboutCommand:
    """Test the 'about' command."""

    def test_cmd_about_runs(self):
        """Test about command executes without error."""
        from scripts.campaign.__main__ import cmd_about

        args = Mock()
        args.json = False

        result = cmd_about(args)
        assert result == 0

    def test_about_output_format(self, capsys):
        """Test about output has expected sections."""
        from scripts.campaign.__main__ import cmd_about

        args = Mock()
        args.json = False

        cmd_about(args)

        captured = capsys.readouterr()
        assert 'ORACLE OF SECRETS' in captured.out
        assert 'Ralph Loop' in captured.out
        assert 'Grand Goals' in captured.out

    def test_about_json_output(self, capsys):
        """Test about JSON output is valid."""
        import json
        from scripts.campaign.__main__ import cmd_about

        args = Mock()
        args.json = True

        result = cmd_about(args)

        assert result == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'name' in data
        assert 'codename' in data
        assert 'grand_goals' in data

    def test_about_arg_parsing(self):
        """Test about argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'about']):
            with patch('scripts.campaign.__main__.cmd_about') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                mock_cmd.assert_called_once()

    def test_about_command_executable(self):
        """Test about command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'about'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'ORACLE OF SECRETS' in result.stdout


class TestCelebrateCommand:
    """Test the 'celebrate' command."""

    def test_cmd_celebrate_runs(self):
        """Test celebrate command executes without error."""
        from scripts.campaign.__main__ import cmd_celebrate

        args = Mock()
        args.json = False

        result = cmd_celebrate(args)
        assert result in [0, 1]  # 0 if reached, 1 if not

    def test_celebrate_output_format(self, capsys):
        """Test celebrate output has expected sections."""
        from scripts.campaign.__main__ import cmd_celebrate

        args = Mock()
        args.json = False

        cmd_celebrate(args)

        captured = capsys.readouterr()
        # Will show either celebration or "not yet reached"
        assert 'MILESTONE' in captured.out or 'CONGRATULATIONS' in captured.out

    def test_celebrate_json_output(self, capsys):
        """Test celebrate JSON output is valid."""
        import json
        from scripts.campaign.__main__ import cmd_celebrate

        args = Mock()
        args.json = True

        cmd_celebrate(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'milestone' in data
        assert 'current' in data
        assert 'reached' in data

    def test_celebrate_arg_parsing(self):
        """Test celebrate argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'celebrate']):
            with patch('scripts.campaign.__main__.cmd_celebrate') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                mock_cmd.assert_called_once()

    def test_celebrate_command_executable(self):
        """Test celebrate command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'celebrate'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        # Will return 0 or 1 depending on milestone status
        assert result.returncode in [0, 1]
        assert 'MILESTONE' in result.stdout or 'CONGRATULATIONS' in result.stdout


class TestStatusCommand:
    """Test the 'status' command."""

    def test_cmd_status_runs(self):
        """Test status command executes without error."""
        from scripts.campaign.__main__ import cmd_status

        # Create mock args
        args = Mock()

        # Should not raise
        cmd_status(args)

    def test_status_output_contains_modules(self, capsys):
        """Test status output mentions key modules."""
        from scripts.campaign.__main__ import cmd_status

        args = Mock()
        cmd_status(args)

        captured = capsys.readouterr()
        output = captured.out

        # Should mention key modules
        assert "EmulatorInterface" in output or "emulator" in output.lower()
        assert "GameStateParser" in output or "state" in output.lower()


class TestCheckCommand:
    """Test the 'check' command."""

    def test_cmd_check_no_sockets(self):
        """Test check command when no sockets exist."""
        from scripts.campaign.__main__ import cmd_check

        args = Mock()

        with patch('glob.glob', return_value=[]):
            result = cmd_check(args)

        # Should return non-zero (no sockets found)
        assert result == 1

    def test_cmd_check_with_stale_socket(self):
        """Test check command with stale socket."""
        from scripts.campaign.__main__ import cmd_check
        import socket

        args = Mock()

        with patch('glob.glob', return_value=['/tmp/mesen2-12345.sock']):
            with patch('socket.socket') as mock_socket:
                mock_sock_instance = Mock()
                mock_sock_instance.connect.side_effect = ConnectionRefusedError()
                mock_socket.return_value = mock_sock_instance

                result = cmd_check(args)

        # Should return non-zero (stale socket)
        assert result == 1


class TestReportCommand:
    """Test the 'report' command."""

    def test_cmd_report_runs(self, capsys):
        """Test report command executes without error."""
        from scripts.campaign.__main__ import cmd_report

        args = Mock()
        cmd_report(args)

        captured = capsys.readouterr()
        output = captured.out

        # Should contain report header
        assert "CAMPAIGN" in output or "PROGRESS" in output or "REPORT" in output

    def test_report_shows_agents(self, capsys):
        """Test report shows agent information."""
        from scripts.campaign.__main__ import cmd_report

        args = Mock()
        cmd_report(args)

        captured = capsys.readouterr()
        output = captured.out

        # Should list agents used
        assert "AGENTS" in output.upper() or "agent" in output.lower()


class TestMainFunction:
    """Test the main entry point."""

    def test_main_no_args_shows_help(self):
        """Test main with no arguments shows help."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign']):
            result = main()

        # Should return 1 (no command given)
        assert result == 1

    def test_main_status_command(self):
        """Test main with status command."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'status']):
            result = main()

        # Should return 0 (success)
        assert result == 0

    def test_main_report_command(self):
        """Test main with report command."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'report']):
            result = main()

        # Should return 0 or None (success)
        assert result == 0 or result is None


class TestRunCommand:
    """Test the 'run' command."""

    def test_cmd_run_connection_failure(self):
        """Test run command handles connection failure."""
        from scripts.campaign.__main__ import cmd_run

        args = Mock()
        args.timeout = 0.1
        args.iterations = 1

        # Patch where create_campaign is imported (scripts.campaign module)
        with patch('scripts.campaign.create_campaign') as mock_create:
            mock_orchestrator = Mock()
            mock_orchestrator.connect.return_value = False
            mock_create.return_value = mock_orchestrator

            result = cmd_run(args)

        # Should return 1 (connection failed)
        assert result == 1


class TestTestCommand:
    """Test the 'test' command."""

    def test_cmd_test_exists(self):
        """Test test command function exists."""
        from scripts.campaign.__main__ import cmd_test
        assert cmd_test is not None

    def test_test_command_args(self):
        """Test test command accepts expected arguments."""
        from scripts.campaign.__main__ import cmd_test

        args = Mock()
        args.quick = False
        args.count = True  # Just collect, don't run

        # This will actually run pytest --collect-only
        # but we're testing the function accepts the args
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            result = cmd_test(args)

        assert result == 0
        mock_run.assert_called_once()


class TestArgumentParsing:
    """Test argument parsing."""

    def test_parser_has_subcommands(self):
        """Test parser has expected subcommands."""
        import argparse
        from scripts.campaign.__main__ import main

        # The main function creates the parser internally
        # We just verify it handles known commands
        commands = ['status', 'test', 'check', 'run', 'report']

        for cmd in commands:
            with patch('sys.argv', ['campaign', cmd]):
                # Mock the actual execution to avoid side effects
                with patch(f'scripts.campaign.__main__.cmd_{cmd}') as mock_cmd:
                    mock_cmd.return_value = 0
                    try:
                        main()
                    except SystemExit:
                        pass  # Some commands may exit

    def test_run_command_has_iterations_arg(self):
        """Test run command accepts --iterations."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'run', '--iterations', '5']):
            with patch('scripts.campaign.__main__.cmd_run') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                # Verify iterations was passed
                args = mock_cmd.call_args[0][0]
                assert args.iterations == 5

    def test_run_command_has_timeout_arg(self):
        """Test run command accepts --timeout."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'run', '--timeout', '10.0']):
            with patch('scripts.campaign.__main__.cmd_run') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                # Verify timeout was passed
                args = mock_cmd.call_args[0][0]
                assert args.timeout == 10.0

    def test_test_command_has_quick_flag(self):
        """Test test command accepts --quick."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'test', '--quick']):
            with patch('scripts.campaign.__main__.cmd_test') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.quick is True


class TestModuleExecution:
    """Test module can be executed directly."""

    def test_module_executable(self):
        """Test module can be run with python -m."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'status'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        # Should succeed (exit code 0)
        assert result.returncode == 0

    def test_module_help(self):
        """Test module shows help with -h."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', '-h'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        # Should succeed
        assert result.returncode == 0
        # Should show help text
        assert 'usage' in result.stdout.lower() or 'campaign' in result.stdout.lower()


class TestStatesCommand:
    """Test the 'states' command."""

    def test_cmd_states_runs(self):
        """Test states command executes without error."""
        from scripts.campaign.__main__ import cmd_states

        args = Mock()
        args.tag = None
        args.verbose = False

        result = cmd_states(args)
        assert result == 0

    def test_cmd_states_with_tag(self):
        """Test states command with tag filter."""
        from scripts.campaign.__main__ import cmd_states

        args = Mock()
        args.tag = "dungeon"
        args.verbose = False

        result = cmd_states(args)
        assert result == 0

    def test_cmd_states_verbose(self):
        """Test states command with verbose flag."""
        from scripts.campaign.__main__ import cmd_states

        args = Mock()
        args.tag = None
        args.verbose = True

        result = cmd_states(args)
        assert result == 0

    def test_states_command_arg_parsing(self):
        """Test states command argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'states', '--tag', 'overworld']):
            with patch('scripts.campaign.__main__.cmd_states') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.tag == 'overworld'

    def test_states_output_contains_entries(self, capsys):
        """Test states command outputs entry information."""
        from scripts.campaign.__main__ import cmd_states

        args = Mock()
        args.tag = None
        args.verbose = False

        cmd_states(args)

        captured = capsys.readouterr()
        # Should contain header info
        assert "ID" in captured.out
        assert "ROM" in captured.out
        # Should contain at least some entries
        assert "baseline" in captured.out or "current" in captured.out


class TestProgressCommand:
    """Test the 'progress' command."""

    def test_cmd_progress_requires_emulator(self):
        """Test progress command fails gracefully without emulator."""
        from scripts.campaign.__main__ import cmd_progress

        args = Mock()
        args.entry = None

        # Mock get_emulator at the module where it's imported from
        with patch('scripts.campaign.get_emulator') as mock_get:
            mock_emu = Mock()
            mock_emu.connect.return_value = False
            mock_get.return_value = mock_emu

            result = cmd_progress(args)
            # Should return 1 (failure) when can't connect
            assert result == 1

    def test_progress_command_arg_parsing(self):
        """Test progress command argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'progress', '--entry', 'baseline_1']):
            with patch('scripts.campaign.__main__.cmd_progress') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.entry == 'baseline_1'

    def test_progress_has_entry_flag(self):
        """Test progress command has --entry flag."""
        import argparse
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'progress', '-e', 'current_1']):
            with patch('scripts.campaign.__main__.cmd_progress') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.entry == 'current_1'


class TestCLINewCommands:
    """Test new CLI commands are registered properly."""

    def test_help_lists_all_commands(self):
        """Test help shows all commands including new ones."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', '--help'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        # Should list new commands
        assert 'progress' in result.stdout
        assert 'states' in result.stdout
        assert 'compare' in result.stdout
        assert 'regression' in result.stdout

    def test_states_command_executable(self):
        """Test states command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'states'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'ID' in result.stdout
        assert 'Total:' in result.stdout


class TestCompareCommand:
    """Test the 'compare' command."""

    def test_cmd_compare_runs(self):
        """Test compare command executes with valid entries."""
        from scripts.campaign.__main__ import cmd_compare

        args = Mock()
        args.entry1 = "baseline_1"
        args.entry2 = "current_1"

        result = cmd_compare(args)
        # Should succeed (entries are equivalent in game state)
        assert result == 0

    def test_cmd_compare_detects_differences(self):
        """Test compare command detects differences."""
        from scripts.campaign.__main__ import cmd_compare

        args = Mock()
        args.entry1 = "baseline_1"  # overworld
        args.entry2 = "baseline_4"  # dungeon

        result = cmd_compare(args)
        # Should return 2 (differences found)
        assert result == 2

    def test_cmd_compare_invalid_entry(self, capsys):
        """Test compare command handles invalid entry."""
        from scripts.campaign.__main__ import cmd_compare

        args = Mock()
        args.entry1 = "nonexistent_entry"
        args.entry2 = "baseline_1"

        result = cmd_compare(args)
        # Should return 1 (error)
        assert result == 1

        captured = capsys.readouterr()
        assert "ERROR" in captured.out
        assert "nonexistent_entry" in captured.out

    def test_compare_command_arg_parsing(self):
        """Test compare command argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'compare', 'baseline_1', 'current_1']):
            with patch('scripts.campaign.__main__.cmd_compare') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.entry1 == 'baseline_1'
                assert args.entry2 == 'current_1'

    def test_compare_output_format(self, capsys):
        """Test compare command output contains expected sections."""
        from scripts.campaign.__main__ import cmd_compare

        args = Mock()
        args.entry1 = "baseline_1"
        args.entry2 = "baseline_4"

        cmd_compare(args)

        captured = capsys.readouterr()
        # Should contain expected sections
        assert "SAVE STATE COMPARISON" in captured.out
        assert "Entry 1:" in captured.out
        assert "Entry 2:" in captured.out
        assert "Game State Comparison:" in captured.out
        assert "Tag Comparison:" in captured.out
        assert "RESULT:" in captured.out

    def test_compare_command_executable(self):
        """Test compare command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'compare', 'baseline_1', 'current_1'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'SAVE STATE COMPARISON' in result.stdout


class TestRegressionCommand:
    """Test the 'regression' command."""

    def test_cmd_regression_runs(self):
        """Test regression command executes without error."""
        from scripts.campaign.__main__ import cmd_regression

        args = Mock()
        args.verbose = False
        args.details = False
        args.tag = None
        args.pattern = None
        args.json = False

        result = cmd_regression(args)
        # Should return 0 (all same) or 2 (differences)
        assert result in [0, 2]

    def test_cmd_regression_verbose(self, capsys):
        """Test regression command with verbose flag."""
        from scripts.campaign.__main__ import cmd_regression

        args = Mock()
        args.verbose = True
        args.details = False
        args.tag = None
        args.pattern = None
        args.json = False

        cmd_regression(args)

        captured = capsys.readouterr()
        assert "REGRESSION TEST" in captured.out
        assert "baseline_" in captured.out
        assert "current_" in captured.out

    def test_cmd_regression_details(self, capsys):
        """Test regression command with details flag."""
        from scripts.campaign.__main__ import cmd_regression

        args = Mock()
        args.verbose = False
        args.details = True
        args.tag = None
        args.pattern = None
        args.json = False

        cmd_regression(args)

        captured = capsys.readouterr()
        assert "SUMMARY:" in captured.out

    def test_regression_finds_pairs(self, capsys):
        """Test regression command finds baseline/current pairs."""
        from scripts.campaign.__main__ import cmd_regression

        args = Mock()
        args.verbose = False
        args.details = False
        args.tag = None
        args.pattern = None
        args.json = False

        cmd_regression(args)

        captured = capsys.readouterr()
        # Should find at least some pairs
        assert "Found" in captured.out
        assert "pairs" in captured.out

    def test_regression_output_format(self, capsys):
        """Test regression command output contains expected sections."""
        from scripts.campaign.__main__ import cmd_regression

        args = Mock()
        args.verbose = False
        args.details = False
        args.tag = None
        args.pattern = None
        args.json = False

        cmd_regression(args)

        captured = capsys.readouterr()
        # Should contain expected sections
        assert "REGRESSION TEST" in captured.out
        assert "Baseline vs Current" in captured.out
        assert "SUMMARY:" in captured.out
        assert "passed" in captured.out

    def test_regression_command_arg_parsing(self):
        """Test regression command argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'regression', '--verbose']):
            with patch('scripts.campaign.__main__.cmd_regression') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.verbose is True

    def test_regression_command_details_flag(self):
        """Test regression command with --details flag."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'regression', '-d']):
            with patch('scripts.campaign.__main__.cmd_regression') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.details is True

    def test_regression_command_executable(self):
        """Test regression command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'regression'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode in [0, 2]  # 0 = all pass, 2 = differences
        assert 'REGRESSION TEST' in result.stdout
        assert 'SUMMARY:' in result.stdout

    def test_regression_with_tag_filter(self, capsys):
        """Test regression command with --tag filter."""
        from scripts.campaign.__main__ import cmd_regression

        args = Mock()
        args.verbose = False
        args.details = False
        args.tag = "dungeon"
        args.pattern = None
        args.json = False

        result = cmd_regression(args)

        captured = capsys.readouterr()
        assert "REGRESSION TEST" in captured.out
        # Should show filter info
        assert "tag=dungeon" in captured.out

    def test_regression_with_pattern_filter(self, capsys):
        """Test regression command with --pattern filter."""
        from scripts.campaign.__main__ import cmd_regression

        args = Mock()
        args.verbose = False
        args.details = False
        args.tag = None
        args.pattern = "water"
        args.json = False

        result = cmd_regression(args)

        captured = capsys.readouterr()
        assert "REGRESSION TEST" in captured.out
        # Should show filter info
        assert "pattern=water" in captured.out

    def test_regression_tag_filter_arg_parsing(self):
        """Test regression command --tag argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'regression', '--tag', 'dungeon']):
            with patch('scripts.campaign.__main__.cmd_regression') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.tag == 'dungeon'

    def test_regression_pattern_filter_arg_parsing(self):
        """Test regression command --pattern argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'regression', '-p', 'zora']):
            with patch('scripts.campaign.__main__.cmd_regression') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.pattern == 'zora'

    def test_regression_no_matches_with_filter(self, capsys):
        """Test regression command with filter that matches nothing."""
        from scripts.campaign.__main__ import cmd_regression

        args = Mock()
        args.verbose = False
        args.details = False
        args.tag = "nonexistent_tag_12345"
        args.pattern = None
        args.json = False

        result = cmd_regression(args)

        # Should return 1 (no pairs found)
        assert result == 1
        captured = capsys.readouterr()
        assert "No baseline/current pairs found" in captured.out

    def test_regression_combined_filters(self):
        """Test regression command with both --tag and --pattern."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'regression', '-t', 'dungeon', '-p', 'water']):
            with patch('scripts.campaign.__main__.cmd_regression') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.tag == 'dungeon'
                assert args.pattern == 'water'

    def test_regression_json_output(self, capsys):
        """Test regression command with --json output."""
        import json
        from scripts.campaign.__main__ import cmd_regression

        args = Mock()
        args.verbose = False
        args.details = False
        args.tag = None
        args.pattern = None
        args.json = True

        result = cmd_regression(args)

        captured = capsys.readouterr()
        # Should be valid JSON
        output = json.loads(captured.out)
        assert 'summary' in output
        assert 'results' in output
        assert output['summary']['total_pairs'] == 11
        assert 'passed' in output['summary']
        assert 'failed' in output['summary']

    def test_regression_json_with_filter(self, capsys):
        """Test regression JSON output includes filter info."""
        import json
        from scripts.campaign.__main__ import cmd_regression

        args = Mock()
        args.verbose = False
        args.details = False
        args.tag = "dungeon"
        args.pattern = None
        args.json = True

        result = cmd_regression(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output['summary']['filters']['tag'] == 'dungeon'

    def test_regression_json_result_structure(self, capsys):
        """Test regression JSON result entries have correct structure."""
        import json
        from scripts.campaign.__main__ import cmd_regression

        args = Mock()
        args.verbose = False
        args.details = False
        args.tag = None
        args.pattern = None
        args.json = True

        cmd_regression(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        # Check first result has expected fields
        result = output['results'][0]
        assert 'baseline_id' in result
        assert 'current_id' in result
        assert 'label' in result
        assert 'status' in result
        assert 'differences' in result

    def test_regression_json_arg_parsing(self):
        """Test regression command --json argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'regression', '--json']):
            with patch('scripts.campaign.__main__.cmd_regression') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.json is True

    def test_regression_json_short_flag(self):
        """Test regression command -j short flag."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'regression', '-j']):
            with patch('scripts.campaign.__main__.cmd_regression') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.json is True


class TestSummaryCommand:
    """Test the 'summary' command."""

    def test_cmd_summary_runs(self):
        """Test summary command executes without error."""
        from scripts.campaign.__main__ import cmd_summary

        args = Mock()
        args.json = False

        result = cmd_summary(args)
        assert result == 0

    def test_summary_output_format(self, capsys):
        """Test summary command output contains expected sections."""
        from scripts.campaign.__main__ import cmd_summary

        args = Mock()
        args.json = False

        cmd_summary(args)

        captured = capsys.readouterr()
        assert "CAMPAIGN SUMMARY" in captured.out
        assert "Iterations:" in captured.out
        assert "Save States:" in captured.out
        assert "Tests:" in captured.out

    def test_summary_json_output(self, capsys):
        """Test summary command JSON output."""
        import json
        from scripts.campaign.__main__ import cmd_summary

        args = Mock()
        args.json = True

        cmd_summary(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert 'timestamp' in output
        assert 'iterations' in output
        assert 'save_states' in output
        assert 'tests' in output

    def test_summary_json_iterations_structure(self, capsys):
        """Test summary JSON iterations has correct fields."""
        import json
        from scripts.campaign.__main__ import cmd_summary

        args = Mock()
        args.json = True

        cmd_summary(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        iterations = output['iterations']
        assert 'overseer' in iterations
        assert 'explorer' in iterations
        assert 'total' in iterations

    def test_summary_json_save_states_structure(self, capsys):
        """Test summary JSON save_states has correct fields."""
        import json
        from scripts.campaign.__main__ import cmd_summary

        args = Mock()
        args.json = True

        cmd_summary(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        states = output['save_states']
        assert 'total' in states
        assert 'baseline' in states
        assert 'current' in states

    def test_summary_arg_parsing(self):
        """Test summary command argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'summary']):
            with patch('scripts.campaign.__main__.cmd_summary') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                mock_cmd.assert_called_once()

    def test_summary_json_flag(self):
        """Test summary command --json flag."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'summary', '--json']):
            with patch('scripts.campaign.__main__.cmd_summary') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.json is True

    def test_summary_command_executable(self):
        """Test summary command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'summary'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'CAMPAIGN SUMMARY' in result.stdout


class TestWatchCommand:
    """Test the 'watch' command."""

    def test_cmd_watch_runs(self):
        """Test watch command executes without error (single iteration)."""
        from scripts.campaign.__main__ import cmd_watch

        args = Mock()
        args.interval = 1
        args.count = 1  # Run only once
        args.no_clear = True

        # Should not raise
        cmd_watch(args)

    def test_watch_output_format(self, capsys):
        """Test watch output has expected sections."""
        from scripts.campaign.__main__ import cmd_watch

        args = Mock()
        args.interval = 1
        args.count = 1
        args.no_clear = True

        cmd_watch(args)

        captured = capsys.readouterr()
        assert 'CAMPAIGN WATCH' in captured.out
        assert 'Iterations:' in captured.out
        assert 'Save States:' in captured.out
        assert 'Tests:' in captured.out
        assert 'Progress to 100 iterations:' in captured.out

    def test_watch_progress_bar(self, capsys):
        """Test watch shows progress bar."""
        from scripts.campaign.__main__ import cmd_watch

        args = Mock()
        args.interval = 1
        args.count = 1
        args.no_clear = True

        cmd_watch(args)

        captured = capsys.readouterr()
        # Progress bar uses block characters
        assert '[' in captured.out and ']' in captured.out
        assert '%' in captured.out

    def test_watch_arg_parsing(self):
        """Test watch argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'watch', '-c', '1', '--no-clear']):
            with patch('scripts.campaign.__main__.cmd_watch') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.count == 1
                assert args.no_clear is True
                assert args.interval == 5  # default

    def test_watch_interval_flag(self):
        """Test watch --interval flag."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'watch', '-i', '10', '-c', '1']):
            with patch('scripts.campaign.__main__.cmd_watch') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.interval == 10

    def test_watch_command_executable(self):
        """Test watch command can be run (single iteration)."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'watch', '-c', '1', '--no-clear'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'CAMPAIGN WATCH' in result.stdout


class TestHistoryCommand:
    """Test the 'history' command."""

    def test_cmd_history_runs(self):
        """Test history command executes without error."""
        from scripts.campaign.__main__ import cmd_history

        args = Mock()
        args.json = False
        args.limit = 10

        result = cmd_history(args)
        assert result == 0

    def test_history_output_format(self, capsys):
        """Test history output has expected sections."""
        from scripts.campaign.__main__ import cmd_history

        args = Mock()
        args.json = False
        args.limit = 10

        cmd_history(args)

        captured = capsys.readouterr()
        assert 'ITERATION HISTORY' in captured.out
        assert 'Total Iterations by Agent:' in captured.out
        assert 'Daily Activity:' in captured.out
        assert 'Recent Iterations:' in captured.out

    def test_history_json_output(self, capsys):
        """Test history JSON output is valid."""
        import json
        from scripts.campaign.__main__ import cmd_history

        args = Mock()
        args.json = True
        args.limit = 10

        cmd_history(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'total_iterations' in data
        assert 'by_agent' in data
        assert 'by_date' in data
        assert 'recent' in data

    def test_history_json_structure(self, capsys):
        """Test history JSON has correct agent breakdown."""
        import json
        from scripts.campaign.__main__ import cmd_history

        args = Mock()
        args.json = True
        args.limit = 10

        cmd_history(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'overseer' in data['by_agent']
        assert 'explorer' in data['by_agent']
        assert isinstance(data['recent'], list)

    def test_history_arg_parsing(self):
        """Test history argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'history']):
            with patch('scripts.campaign.__main__.cmd_history') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.json is False
                assert args.limit == 10

    def test_history_limit_flag(self):
        """Test history --limit flag."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'history', '-l', '5']):
            with patch('scripts.campaign.__main__.cmd_history') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.limit == 5

    def test_history_command_executable(self):
        """Test history command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'history'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'ITERATION HISTORY' in result.stdout


class TestGoalsCommand:
    """Test the 'goals' command."""

    def test_cmd_goals_runs(self):
        """Test goals command executes without error."""
        from scripts.campaign.__main__ import cmd_goals

        args = Mock()
        args.json = False
        args.verbose = False

        result = cmd_goals(args)
        assert result == 0

    def test_goals_output_format(self, capsys):
        """Test goals output has expected sections."""
        from scripts.campaign.__main__ import cmd_goals

        args = Mock()
        args.json = False
        args.verbose = False

        cmd_goals(args)

        captured = capsys.readouterr()
        assert 'CAMPAIGN GOALS' in captured.out
        assert 'Goal A:' in captured.out
        assert 'Goal B:' in captured.out
        assert 'Goal C:' in captured.out
        assert 'Goal D:' in captured.out
        assert 'Goal E:' in captured.out
        assert 'Overall Progress:' in captured.out

    def test_goals_verbose_output(self, capsys):
        """Test goals verbose shows milestones."""
        from scripts.campaign.__main__ import cmd_goals

        args = Mock()
        args.json = False
        args.verbose = True

        cmd_goals(args)

        captured = capsys.readouterr()
        # Verbose mode shows checkmarks
        assert '✓' in captured.out or '○' in captured.out

    def test_goals_json_output(self, capsys):
        """Test goals JSON output is valid."""
        import json
        from scripts.campaign.__main__ import cmd_goals

        args = Mock()
        args.json = True
        args.verbose = False

        cmd_goals(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'goals' in data
        assert 'A' in data['goals']
        assert 'B' in data['goals']

    def test_goals_json_structure(self, capsys):
        """Test goals JSON has correct structure."""
        import json
        from scripts.campaign.__main__ import cmd_goals

        args = Mock()
        args.json = True
        args.verbose = False

        cmd_goals(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        goal_a = data['goals']['A']
        assert 'name' in goal_a
        assert 'description' in goal_a
        assert 'completed' in goal_a
        assert 'total' in goal_a
        assert 'percent' in goal_a
        assert 'milestones' in goal_a

    def test_goals_arg_parsing(self):
        """Test goals argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'goals']):
            with patch('scripts.campaign.__main__.cmd_goals') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.json is False
                assert args.verbose is False

    def test_goals_verbose_flag(self):
        """Test goals --verbose flag."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'goals', '-v']):
            with patch('scripts.campaign.__main__.cmd_goals') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.verbose is True

    def test_goals_command_executable(self):
        """Test goals command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'goals'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'CAMPAIGN GOALS' in result.stdout


class TestDashboardCommand:
    """Test the 'dashboard' command."""

    def test_cmd_dashboard_runs(self):
        """Test dashboard command executes without error."""
        from scripts.campaign.__main__ import cmd_dashboard

        args = Mock()
        args.json = False

        result = cmd_dashboard(args)
        assert result == 0

    def test_dashboard_output_format(self, capsys):
        """Test dashboard output has expected sections."""
        from scripts.campaign.__main__ import cmd_dashboard

        args = Mock()
        args.json = False

        cmd_dashboard(args)

        captured = capsys.readouterr()
        assert 'CAMPAIGN DASHBOARD' in captured.out
        assert 'ITERATIONS TO 100' in captured.out
        assert 'GRAND GOALS' in captured.out
        assert 'INFRASTRUCTURE' in captured.out
        assert 'STATUS' in captured.out

    def test_dashboard_json_output(self, capsys):
        """Test dashboard JSON output is valid."""
        import json
        from scripts.campaign.__main__ import cmd_dashboard

        args = Mock()
        args.json = True

        cmd_dashboard(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'timestamp' in data
        assert 'iterations' in data
        assert 'save_states' in data
        assert 'tests' in data
        assert 'goals' in data

    def test_dashboard_json_structure(self, capsys):
        """Test dashboard JSON has correct structure."""
        import json
        from scripts.campaign.__main__ import cmd_dashboard

        args = Mock()
        args.json = True

        cmd_dashboard(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert 'overseer' in data['iterations']
        assert 'explorer' in data['iterations']
        assert 'total' in data['iterations']
        assert 'baseline' in data['save_states']
        assert 'current' in data['save_states']

    def test_dashboard_arg_parsing(self):
        """Test dashboard argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'dashboard']):
            with patch('scripts.campaign.__main__.cmd_dashboard') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.json is False

    def test_dashboard_command_executable(self):
        """Test dashboard command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'dashboard'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        assert result.returncode == 0
        assert 'CAMPAIGN DASHBOARD' in result.stdout


class TestValidateCommand:
    """Test the 'validate' command."""

    def test_cmd_validate_runs(self):
        """Test validate command executes without error."""
        from scripts.campaign.__main__ import cmd_validate

        args = Mock()
        args.json = False

        result = cmd_validate(args)
        # Should return 0 (valid) or 1 (errors)
        assert result in [0, 1]

    def test_validate_output_format(self, capsys):
        """Test validate command output contains expected sections."""
        from scripts.campaign.__main__ import cmd_validate

        args = Mock()
        args.json = False

        cmd_validate(args)

        captured = capsys.readouterr()
        assert "SAVE STATE LIBRARY VALIDATION" in captured.out
        assert "Entries:" in captured.out

    def test_validate_json_output(self, capsys):
        """Test validate command JSON output."""
        import json
        from scripts.campaign.__main__ import cmd_validate

        args = Mock()
        args.json = True

        cmd_validate(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert 'valid' in output
        assert 'entries_count' in output
        assert 'errors' in output
        assert 'warnings' in output

    def test_validate_json_structure(self, capsys):
        """Test validate JSON has correct types."""
        import json
        from scripts.campaign.__main__ import cmd_validate

        args = Mock()
        args.json = True

        cmd_validate(args)

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert isinstance(output['valid'], bool)
        assert isinstance(output['entries_count'], int)
        assert isinstance(output['errors'], list)
        assert isinstance(output['warnings'], list)

    def test_validate_arg_parsing(self):
        """Test validate command argument parsing."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'validate']):
            with patch('scripts.campaign.__main__.cmd_validate') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                mock_cmd.assert_called_once()

    def test_validate_json_flag(self):
        """Test validate command --json flag."""
        from scripts.campaign.__main__ import main

        with patch('sys.argv', ['campaign', 'validate', '--json']):
            with patch('scripts.campaign.__main__.cmd_validate') as mock_cmd:
                mock_cmd.return_value = 0
                main()

                args = mock_cmd.call_args[0][0]
                assert args.json is True

    def test_validate_command_executable(self):
        """Test validate command can be run."""
        result = subprocess.run(
            [sys.executable, '-m', 'scripts.campaign', 'validate'],
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )

        # May return 0 or 1 depending on library state
        assert result.returncode in [0, 1]
        assert 'SAVE STATE LIBRARY VALIDATION' in result.stdout
