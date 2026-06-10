from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol

import paramiko

from wanusage.config import RouterConfig


class RemoteCommandError(RuntimeError):
    pass


class RemoteCommandRunner(Protocol):
    def run(self, command: str) -> str:
        ...


class ReadableStream(Protocol):
    def read(self) -> bytes:
        ...


@dataclass(frozen=True)
class ParamikoCommandRunner:
    router_config: RouterConfig
    timeout_seconds: int = 30

    def run(self, command: str) -> str:
        client: paramiko.SSHClient = paramiko.SSHClient()

        try:
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
            client.connect(
                hostname=self.router_config.host,
                port=self.router_config.port,
                username=self.router_config.username,
                key_filename=str(self.router_config.ssh_key_path),
                timeout=self.timeout_seconds,
                banner_timeout=self.timeout_seconds,
                auth_timeout=self.timeout_seconds,
            )
            _stdin, stdout, stderr = client.exec_command(command, timeout=self.timeout_seconds)
            with ThreadPoolExecutor(max_workers=2) as executor:
                stdout_future: Future[bytes] = executor.submit(_read_stream, stdout)
                stderr_future: Future[bytes] = executor.submit(_read_stream, stderr)
                stdout_bytes: bytes = stdout_future.result()
                stderr_bytes: bytes = stderr_future.result()

            exit_status: int = stdout.channel.recv_exit_status()
            stdout_text: str = stdout_bytes.decode("utf-8", errors="replace")
            stderr_text: str = stderr_bytes.decode("utf-8", errors="replace")
        except (paramiko.SSHException, OSError) as error:
            raise RemoteCommandError(
                "SSH operation failed for "
                f"{self.router_config.host}:{self.router_config.port}: {error}"
            ) from error
        finally:
            client.close()

        if exit_status != 0:
            raise RemoteCommandError(
                f"Remote command failed with exit status {exit_status}: {stderr_text.strip()}"
            )

        return stdout_text


def _read_stream(stream: ReadableStream) -> bytes:
    return stream.read()
