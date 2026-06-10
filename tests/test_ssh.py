from __future__ import annotations

from pathlib import Path

import paramiko
import pytest

from wanusage.config import RouterConfig
from wanusage.ssh import ParamikoCommandRunner, RemoteCommandError


class FakeChannel:
    def __init__(self, exit_status: int, *, require_streams_read: bool = False) -> None:
        self.exit_status: int = exit_status
        self.require_streams_read: bool = require_streams_read
        self.streams_read: set[str] = set()

    def recv_exit_status(self) -> int:
        if self.require_streams_read and self.streams_read != {"stdout", "stderr"}:
            raise AssertionError("exit status requested before streams were read")
        return self.exit_status


class FakeStream:
    def __init__(self, name: str, content: bytes, channel: FakeChannel) -> None:
        self.name: str = name
        self.content: bytes = content
        self.channel: FakeChannel = channel

    def read(self) -> bytes:
        self.channel.streams_read.add(self.name)
        return self.content


class FakeSshClient:
    instances: list[FakeSshClient] = []
    connect_error: Exception | None = None
    stdout_content: bytes = b"output"
    stderr_content: bytes = b""
    exit_status: int = 0
    require_streams_read: bool = False

    def __init__(self) -> None:
        self.closed: bool = False
        self.loaded_host_keys: bool = False
        self.host_key_policy: object | None = None
        FakeSshClient.instances.append(self)

    def load_system_host_keys(self) -> None:
        self.loaded_host_keys = True

    def set_missing_host_key_policy(self, policy: object) -> None:
        self.host_key_policy = policy

    def connect(self, **_kwargs: object) -> None:
        if self.connect_error is not None:
            raise self.connect_error

    def exec_command(
        self,
        _command: str,
        *,
        timeout: int,
    ) -> tuple[FakeStream, FakeStream, FakeStream]:
        del timeout
        channel = FakeChannel(
            self.exit_status,
            require_streams_read=self.require_streams_read,
        )
        return (
            FakeStream("stdin", b"", channel),
            FakeStream("stdout", self.stdout_content, channel),
            FakeStream("stderr", self.stderr_content, channel),
        )

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def reset_fake_ssh_client() -> None:
    FakeSshClient.instances = []
    FakeSshClient.connect_error = None
    FakeSshClient.stdout_content = b"output"
    FakeSshClient.stderr_content = b""
    FakeSshClient.exit_status = 0
    FakeSshClient.require_streams_read = False


def _runner() -> ParamikoCommandRunner:
    return ParamikoCommandRunner(
        RouterConfig(
            host="router.example.com",
            port=22,
            username="root",
            ssh_key_path=Path("/tmp/router-key"),
        )
    )


def test_run_wraps_paramiko_connection_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeSshClient.connect_error = paramiko.AuthenticationException(
        "Authentication failed"
    )
    monkeypatch.setattr("wanusage.ssh.paramiko.SSHClient", FakeSshClient)

    with pytest.raises(
        RemoteCommandError,
        match=r"SSH operation failed for router\.example\.com:22",
    ):
        _runner().run("true")

    assert FakeSshClient.instances[0].closed is True


def test_run_wraps_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSshClient.connect_error = TimeoutError("Connection timed out")
    monkeypatch.setattr("wanusage.ssh.paramiko.SSHClient", FakeSshClient)

    with pytest.raises(RemoteCommandError, match="Connection timed out"):
        _runner().run("true")

    assert FakeSshClient.instances[0].closed is True


def test_run_preserves_remote_command_failure_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeSshClient.exit_status = 2
    FakeSshClient.stderr_content = b"sqlite failed"
    monkeypatch.setattr("wanusage.ssh.paramiko.SSHClient", FakeSshClient)

    with pytest.raises(
        RemoteCommandError,
        match="Remote command failed with exit status 2: sqlite failed",
    ):
        _runner().run("false")

    assert FakeSshClient.instances[0].closed is True


def test_run_drains_stdout_and_stderr_before_waiting_for_exit_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeSshClient.require_streams_read = True
    FakeSshClient.stdout_content = b"x" * 100_000
    FakeSshClient.stderr_content = b"y" * 100_000
    monkeypatch.setattr("wanusage.ssh.paramiko.SSHClient", FakeSshClient)

    output: str = _runner().run("large-output-command")

    assert output == "x" * 100_000
    assert FakeSshClient.instances[0].closed is True
