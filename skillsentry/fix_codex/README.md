# fix_codex

Fixes the bug in codex 0.135.0 where hooks do not fire in `exec` mode, and provides a complete integration solution with Harbor.

---

## Directory Structure

```
fix_codex/
├── README.md                  # This document
├── setup.sh                   # One-click install script; just run this on a new machine
├── codex-fixed                # Fixed codex core binary (198MB, x86_64 Linux)
├── Dockerfile.base            # Builds the codex-base:0.135.0 image, shared by all tasks
├── agent.py                   # Harbor custom agent (PatchedCodexAgent)
├── __init__.py                # Makes fix_codex importable as a Python package by harbor
├── example/
│   ├── job_template.yaml      # Job config template; copy and fill in API key and paths
│   ├── job_econ_iter0.yaml    # Example job (for validation; requires API key and paths)
│   ├── job_hooks_test.yaml    # Hooks verification job (requires API key and paths)
│   └── hooks.json             # Example hooks config that logs each tool call
└── task_econ_iter0/           # Example task (econ-detrending-correlation)
    ├── environment/
    │   └── Dockerfile         # FROM codex-base:0.135.0, adds only task-specific deps
    ├── instruction.md         # Task instructions
    └── task.toml              # Task configuration
```

---

## Background: What Was Fixed

**Bug**: When using `codex exec` (non-interactive mode), all configured hooks (SessionStart, PreToolUse, PostToolUse, etc.) do not fire, even with the `--dangerously-bypass-hook-trust` flag.

**Root cause**: `thread_start_params_from_config()` in `codex-rs/exec/src/lib.rs` does not pass `bypass_hook_trust=true` when building the request sent to the app-server. The app-server reloads the config and the value reverts to `false`, causing all hooks to be filtered out by the trust check.

**Fix**: Modified the source code and recompiled; the resulting binary is `codex-fixed` (198MB). `Dockerfile.base` replaces the npm-installed original binary with this fixed version during image build.

**Note**: `codex-fixed` is compiled for x86_64-linux-musl and only supports x86_64 Linux. For ARM machines, recompile from source (see end of document).

---

## Installation

### Prerequisites

- **x86_64 Linux** (`uname -m` outputs `x86_64`)
- **Docker** (`docker --version` works normally)
- **Harbor >= 0.1.45**, install with: `uv tool install harbor`

### Step 1: Prepare the codex-fixed binary

Place the fixed binary in the `fix_codex/` root directory; the default filename is `codex-fixed`.

If the file you received has a different name, you have two options:

```bash
# Option 1: Rename to codex-fixed
mv your_binary_file fix_codex/codex-fixed

# Option 2: Keep the original name and specify it via environment variable
# No renaming needed; specify it when running setup.sh (see Step 2)
```

### Step 2: Run the install script

```bash
cd fix_codex

# Filename is codex-fixed (default)
bash setup.sh

# Filename is something else
CODEX_BINARY=your_binary_file bash setup.sh
```

Successful installation looks like:

```
[setup] fix_codex dir: /your/path/fix_codex
[setup] arch: x86_64 OK
[setup] checking prerequisites...
[setup] harbor Python: /path/to/harbor/python
[setup] fix_codex already registered in harbor Python env
[setup] import OK
[setup] using patched binary: codex-fixed
[setup] codex-base:0.135.0 already exists, skipping build
[setup] verifying base image...
codex-cli 0.0.0
[setup] codex OK in image

✓ Setup complete.
```

The first run builds the image in about 5 minutes (mainly `npm install codex`); subsequent runs complete instantly.

---

## API Configuration

SkillSentry works with any OpenAI-compatible API. Configure the following two parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `V_API_KEY` / `OPENAI_API_KEY` | API key; set both to the same value | `sk-xxxxxxxx` |
| `OPENAI_BASE_URL` | API endpoint, append `/v1` | `https://api.example.com/v1` |

**Configure in job yaml** (recommended; each job configured independently):

```yaml
agents:
  - name: codex-patched
    import_path: fix_codex.agent:PatchedCodexAgent
    model_name: openai/gpt-5.2-medium
    env:
      V_API_KEY: "sk-your-key-here"
      OPENAI_API_KEY: "sk-your-key-here"
      OPENAI_BASE_URL: "https://api.example.com/v1"
```

**Or pass via environment variables** (overrides at runtime):

```bash
V_API_KEY=sk-xxx OPENAI_API_KEY=sk-xxx harbor run -c my_job.yaml
```

---

## Verification

Run the following checks in order to confirm each component works correctly.

### Check 1: Image and Python package (no API key needed, completes instantly)

```bash
# Check image exists
docker images | grep codex-base

# Check Python package can be imported
HARBOR_PYTHON=$(head -1 $(which harbor) | sed 's/^#!//')
$HARBOR_PYTHON -c "from fix_codex.agent import PatchedCodexAgent; print('OK')"
```

Expected output:
```
codex-base   0.135.0   <image-id>   ...
OK
```

### Check 2: codex works inside the image (no API key needed, completes instantly)

```bash
docker run --rm codex-base:0.135.0 sh -c \
  '. ~/.nvm/nvm.sh && codex --version'
```

Expected output:
```
codex-cli 0.0.0
```

> Showing version `0.0.0` is normal; the version was not set during source compilation, but functionality is equivalent to 0.135.0 + the fix.

### Check 3: Run a full task (requires API key, about 3 minutes)

**3a. Copy and fill in job config**

```bash
cp example/job_econ_iter0.yaml my_job.yaml
```

Open `my_job.yaml` in an editor and replace the following placeholders:

```yaml
jobs_dir: REPLACE_WITH_FIX_CODEX_DIR/jobs
      V_API_KEY: "REPLACE_WITH_YOUR_API_KEY"
      OPENAI_API_KEY: "REPLACE_WITH_YOUR_API_KEY"
  - path: REPLACE_WITH_FIX_CODEX_DIR/task_econ_iter0
```

Replacement rules:
- `REPLACE_WITH_YOUR_API_KEY` → your API key, e.g. `sk-xxxxxxxx`
- `REPLACE_WITH_FIX_CODEX_DIR` → absolute path to the fix_codex directory, e.g. `/home/user/fix_codex`

**3b. Build the task image**

```bash
docker build -t hb__task-econ-iter0 task_econ_iter0/environment/
```

**3c. Run**

```bash
harbor run -c my_job.yaml
```

Expected output (after about 3 minutes):
```
Mean: 1.000
  reward = 1.0   1
```

`reward = 1.0` means codex solved the task correctly and the entire pipeline is working.

### Check 4: Verify hooks fire (requires API key, about 3 minutes)

**4a. Copy and fill in hooks test job**

```bash
cp example/job_hooks_test.yaml my_hooks_job.yaml
```

Replace `REPLACE_WITH_YOUR_API_KEY` and `REPLACE_WITH_FIX_CODEX_DIR` as above.

**4b. Run**

```bash
harbor run -c my_hooks_job.yaml
```

**4c. Check hook log**

```bash
cat jobs/codex-hooks-test/*/agent/hook.log
```

Expected output:
```
[2026-...] session_start
[2026-...] user_prompt_submit
[2026-...] pre_tool_use tool=Bash cmd=ls -al /root
[2026-...] post_tool_use tool=Bash
[2026-...] pre_tool_use tool=Bash cmd=python3 ...
[2026-...] post_tool_use tool=Bash
...
[2026-...] stop
```

Seeing `session_start`, `pre_tool_use`, `post_tool_use`, and `stop` all recorded means the hooks fix is fully working.

---

## Using in Your Own Task

### Task Dockerfile

Change the first line to `FROM codex-base:0.135.0` and write the rest normally:

```dockerfile
FROM codex-base:0.135.0

# Task-specific dependencies
RUN pip3 install pandas scipy numpy

# Data files
COPY data.csv /root/

# Skills (optional)
COPY skills /root/.codex/skills
```

### Job yaml

Copy `example/job_template.yaml` and fill in the following fields:

```yaml
job_name: my-job-name
jobs_dir: /path/to/output/jobs   # Output directory for results

agents:
  - name: codex-patched
    import_path: fix_codex.agent:PatchedCodexAgent   # Must use this agent
    model_name: openai/gpt-5.2-medium
    env:
      V_API_KEY: "sk-your-key"
      OPENAI_API_KEY: "sk-your-key"
      OPENAI_BASE_URL: "https://api.example.com/v1"
      CODEX_HOOKS_CONFIG: "/path/to/hooks.json"      # Optional; enables hooks

tasks:
  - path: /path/to/your/task
```

### Output Structure

Output is in `jobs_dir/<job_name>/<trial_name>/`:

```
jobs/my-job-name/task__xxxxx/
├── agent/
│   ├── codex.txt        # Full codex exec output (includes HOOK_DEBUG info)
│   ├── hook.log         # Hook trigger log (only present if CODEX_HOOKS_CONFIG is set)
│   └── trajectory.json  # Trajectory file
├── verifier/            # pytest verification results
└── result.json          # Final reward
```

---

## Troubleshooting

**`codex-fixed: not found` build error**
→ Confirm `codex-fixed` (or your binary) is in the `fix_codex/` root directory, and `docker build` is run from that directory.

**`from fix_codex.agent import PatchedCodexAgent` fails**
→ Re-run `bash setup.sh`; it will rebuild the symlink.

**`codex --version` shows `0.0.0`**
→ Normal; version was not set during source compilation; functionality is equivalent to 0.135.0 + fix.

**Hooks not firing (`discovered handlers=0`)**
→ Check `[HOOK_DEBUG]` output in `agent/codex.txt`; confirm `bypass_hook_trust=true`.
→ If it is `false`, check that `import_path` in the job yaml is `fix_codex.agent:PatchedCodexAgent`.

**401 Unauthorized**
→ API key has expired; update `V_API_KEY` and `OPENAI_API_KEY` in the job yaml.

**Architecture not supported (non-x86_64)**
→ `codex-fixed` only supports x86_64 Linux; ARM machines must recompile from source (see below).

---

## Recompiling from Source (ARM or Other Architectures)

```bash
# 1. Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 2. Clone codex source
git clone --depth=1 https://github.com/openai/codex.git
cd codex/codex-rs

# 3. Apply the fix in thread_start_params_from_config() in exec/src/lib.rs
#    (see "Fix Details" below)

# 4. Compile (about 30-40 minutes)
cargo build --release -p codex-cli

# 5. Place the output in the fix_codex directory
cp target/release/codex /path/to/fix_codex/codex-fixed

# 6. Rebuild the image
cd /path/to/fix_codex
docker rmi codex-base:0.135.0 2>/dev/null || true
bash setup.sh
```

---

## Fix Details (for reference)

File: `codex-rs/exec/src/lib.rs`, function: `thread_start_params_from_config()`

```rust
// Before fix
ThreadStartParams {
    ...
    config: None,
    ...
}

// After fix
let config_overrides = if config.bypass_hook_trust {
    let mut map = std::collections::HashMap::new();
    map.insert(
        "bypass_hook_trust".to_string(),
        serde_json::Value::Bool(true),
    );
    Some(map)
} else {
    None
};
ThreadStartParams {
    ...
    config: config_overrides,
    ...
}
```
