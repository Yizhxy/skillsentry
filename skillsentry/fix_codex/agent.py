"""
Patched Harbor Codex agent that fixes hook execution in codex exec mode.

Root cause: codex 0.135.0 has a bug where --dangerously-bypass-hook-trust is
not forwarded from the exec CLI process to the app-server thread/start request.
The app-server reloads config for the session and bypass_hook_trust defaults to
false, causing all hooks to be filtered out by the trust check.

Fix: use a pre-built Docker image with the patched binary, and pass
--dangerously-bypass-hook-trust so it flows through correctly.

Usage in harbor job yaml:
    agents:
    - name: codex-patched
      import_path: fix_codex.agent:PatchedCodexAgent
      model_name: openai/gpt-5.2-medium
      kwargs:
        version: "0.135.0-patched"

Also set docker_image in task.toml [environment]:
    [environment]
    docker_image = "codex-hooks-patched:0.135.0"
"""

import os
import shlex
from pathlib import Path

from harbor.agents.installed.codex import Codex
from harbor.agents.installed.base import ExecInput
from harbor.models.trial.paths import EnvironmentPaths


class PatchedCodexAgent(Codex):
    """
    Codex agent with hooks enabled.

    Differences from the stock Codex agent:
    1. Uses a pre-built image (set docker_image in task.toml) with the patched
       binary — no reinstall needed, setup() is a no-op.
    2. Passes --dangerously-bypass-hook-trust to codex exec.
    3. Injects hooks config from CODEX_HOOKS_CONFIG env var (path to a
       hooks.json file on the host) into CODEX_HOME inside the container.
    4. Uses V_API_KEY / OPENAI_BASE_URL for third-party API providers.
    """

    @property
    def _install_agent_template_path(self) -> Path:
        """
        Return a no-op install script — the image already has codex installed.
        Writing to /tmp avoids touching the harbor package directory.
        """
        script = Path("/tmp/_codex_noop_install.sh")
        script.write_text(
            "#!/bin/bash\n"
            ". ~/.nvm/nvm.sh\n"
            "echo '[fix_codex] codex pre-installed in image, skipping reinstall'\n"
            "codex --version\n"
        )
        return script

    def create_run_agent_commands(self, instruction: str) -> list[ExecInput]:
        escaped_instruction = shlex.quote(instruction)

        if not self.model_name:
            raise ValueError("Model name is required")

        model = self.model_name.split("/")[-1]

        # Support V_API_KEY for third-party providers (OpenAI-compatible endpoints)
        # _extra_env comes from job yaml agents.env — check it first, then os.environ
        extra = getattr(self, "_extra_env", {})
        api_key = (
            extra.get("V_API_KEY")
            or extra.get("OPENAI_API_KEY")
            or os.environ.get("V_API_KEY")
            or os.environ.get("OPENAI_API_KEY", "")
        )
        base_url = (
            extra.get("OPENAI_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL", "YOUR_API_BASE_URL")
        )
        env = {
            "OPENAI_API_KEY": api_key,
            "V_API_KEY": api_key,
            "CODEX_HOME": EnvironmentPaths.agent_dir.as_posix(),
        }

        reasoning_effort = self._reasoning_effort
        reasoning_flag = (
            f"-c model_reasoning_effort={reasoning_effort} " if reasoning_effort else ""
        )

        # Build auth.json for codex
        auth_json = f'{{"OPENAI_API_KEY": "{api_key}", "V_API_KEY": "{api_key}"}}'

        # Write config.toml with vapi provider into CODEX_HOME
        import base64
        config_toml = (
            'model_provider = "vapi"\n'
            f'model = "{model}"\n'
            "\n"
            "[model_providers.vapi]\n"
            'name = "VAPI"\n'
            f'base_url = "{base_url}"\n'
            'env_key = "V_API_KEY"\n'
            'wire_api = "responses"\n'
            "\n"
            '[projects."/"]\n'
            'trust_level = "trusted"\n'
        )
        config_b64 = base64.b64encode(config_toml.encode()).decode()

        # Optionally inject hooks.json from host via CODEX_HOOKS_CONFIG env var
        hooks_inject = ""
        hooks_config_path = (
            extra.get("CODEX_HOOKS_CONFIG")
            or os.environ.get("CODEX_HOOKS_CONFIG", "")
        )
        if hooks_config_path and Path(hooks_config_path).exists():
            hooks_b64 = base64.b64encode(Path(hooks_config_path).read_bytes()).decode()
            hooks_inject = f'\necho "{hooks_b64}" | base64 -d > "$CODEX_HOME/hooks.json"'

        setup_command = (
            "mkdir -p /tmp/codex-secrets\n"
            f"echo '{auth_json}' > /tmp/codex-secrets/auth.json\n"
            'ln -sf /tmp/codex-secrets/auth.json "$CODEX_HOME/auth.json"\n'
            f'echo "{config_b64}" | base64 -d > "$CODEX_HOME/config.toml"'
            + hooks_inject
        )

        mcp_command = self._build_register_mcp_servers_command()
        if mcp_command:
            setup_command += f"\n{mcp_command}"

        run_command = (
            "trap 'rm -rf /tmp/codex-secrets \"$CODEX_HOME/auth.json\"' EXIT TERM INT; "
            ". ~/.nvm/nvm.sh; "
            "codex exec "
            "--dangerously-bypass-approvals-and-sandbox "
            "--dangerously-bypass-hook-trust "
            "--skip-git-repo-check "
            "--json "
            "--enable unified_exec "
            f"{reasoning_flag}"
            "-- "
            f"{escaped_instruction} "
            f"2>&1 </dev/null | stdbuf -oL tee {EnvironmentPaths.agent_dir / self._OUTPUT_FILENAME}"
        )

        return [
            ExecInput(command=setup_command, env=env),
            ExecInput(command=run_command, env=env),
        ]
