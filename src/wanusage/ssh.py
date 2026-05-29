from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import paramiko

from wanusage.config import RouterConfig


class RemoteCommandError(RuntimeError):
    pass


class RemoteCommandRunner(Protocol):
    def run(self, command: str) -> str:
        ...


@dataclass(frozen=True)
class ParamikoCommandRunner:
    router_config: RouterConfig
    timeout_seconds: int = 30

    def run(self, command: str) -> str:
        client: paramiko.SSHClient = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())

        try:
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
            exit_status: int = stdout.channel.recv_exit_status()
            stdout_text: str = stdout.read().decode("utf-8", errors="replace")
            stderr_text: str = stderr.read().decode("utf-8", errors="replace")
        finally:
            client.close()

        if exit_status != 0:
            raise RemoteCommandError(
                f"Remote command failed with exit status {exit_status}: {stderr_text.strip()}"
            )

        return stdout_text
