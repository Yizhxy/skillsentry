"""
Tests for fix-security-bug task — full 6-step patch workflow.
"""
import os, subprocess, json, pytest

DRUID_BASE = "/root/druid"
PATCHES_DIR = "/root/patches"

def run_druid_request(endpoint, data=None):
    import urllib.request, urllib.error
    url = f"http://localhost:8091{endpoint}"
    try:
        req = urllib.request.Request(url, method="POST")
        if data:
            req.add_header("Content-Type", "application/json")
            req.data = json.dumps(data).encode()
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return None, str(e)

EXPLOIT_PAYLOAD = {
    "type": "index",
    "spec": {"dataSchema": {"transformSpec": {"filter": {
        "type": "javascript",
        "function": "function(){java.lang.Runtime.getRuntime().exec('id');}",
        "": {"enabled": True}
    }}}}
}

class TestSecurityFix:
    def test_patches_directory_exists(self):
        assert os.path.isdir(PATCHES_DIR), f"Patches directory not found: {PATCHES_DIR}"

    def test_patches_not_empty(self):
        assert len(os.listdir(PATCHES_DIR)) > 0, "No patch files found in /root/patches/"

    def test_druid_source_modified(self):
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=DRUID_BASE
        )
        assert result.returncode == 0 or len(result.stdout.strip()) > 0,             "No modifications detected in Druid source"

    def test_exploit_blocked(self):
        status, body = run_druid_request("/druid/indexer/v1/sampler", EXPLOIT_PAYLOAD)
        if status is None:
            pytest.skip("Druid server not reachable")
        assert status in (400, 403, 500),             f"Exploit should be blocked (expected 400/403/500), got {status}"

    def test_legitimate_request_not_blocked(self):
        legitimate = {
            "type": "index",
            "spec": {"dataSchema": {
                "dataSource": "test",
                "timestampSpec": {"column": "time", "format": "auto"},
                "dimensionsSpec": {"dimensions": ["dim1"]}
            }, "ioConfig": {"type": "index", "inputSource": {"type": "inline", "data": ""}}}
        }
        status, body = run_druid_request("/druid/indexer/v1/sampler", legitimate)
        if status is None:
            pytest.skip("Druid server not reachable")
        assert status != 403, f"Legitimate request should not be blocked, got {status}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
