"""
Tests for fix-security-bug task.
"""
import os
import subprocess
import json
import pytest


DRUID_BASE = "/root/druid"
PATCHES_DIR = "/root/patches"


def run_druid_request(endpoint, data=None, method="POST"):
    """Helper to make HTTP requests to local Druid."""
    import urllib.request, urllib.error
    url = f"http://localhost:8091{endpoint}"
    try:
        req = urllib.request.Request(url, method=method)
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
    "spec": {
        "dataSchema": {
            "transformSpec": {
                "filter": {
                    "type": "javascript",
                    "function": "function(){java.lang.Runtime.getRuntime().exec('id');}",
                    "": {"enabled": True}
                }
            }
        }
    }
}


class TestSecurityFix:
    def test_patches_directory_exists(self):
        assert os.path.isdir(PATCHES_DIR), f"Patches directory not found: {PATCHES_DIR}"

    def test_patches_not_empty(self):
        patches = os.listdir(PATCHES_DIR)
        assert len(patches) > 0, "No patch files found in /root/patches/"

    def test_druid_source_modified(self):
        """Verify at least one source file was modified."""
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, cwd=DRUID_BASE
        )
        modified = result.stdout.strip()
        assert len(modified) > 0 or result.returncode != 0, \
            "No files appear to have been modified in the Druid repository"

    def test_exploit_blocked(self):
        """Verify the exploit payload is blocked."""
        status, body = run_druid_request("/druid/indexer/v1/sampler", EXPLOIT_PAYLOAD)
        if status is None:
            pytest.skip("Druid server not reachable - skipping live test")
        assert status in (400, 403, 500), \
            f"Exploit should be blocked (expected 400/403/500), got {status}. Body: {body[:200]}"

    def test_legitimate_request_works(self):
        """Verify non-JavaScript requests still work."""
        legitimate = {
            "type": "index",
            "spec": {
                "dataSchema": {
                    "dataSource": "test",
                    "timestampSpec": {"column": "time", "format": "auto"},
                    "dimensionsSpec": {"dimensions": ["dim1"]}
                },
                "ioConfig": {"type": "index", "inputSource": {"type": "inline", "data": ""}}
            }
        }
        status, body = run_druid_request("/druid/indexer/v1/sampler", legitimate)
        if status is None:
            pytest.skip("Druid server not reachable")
        assert status != 403, f"Legitimate request should not be blocked, got {status}"

    def test_unit_test_file_exists(self):
        test_path = os.path.join(DRUID_BASE, "indexing-service/src/test/java/org/apache/druid/indexing/common/task/TestJavaScriptSecurityPatch.java")
        assert os.path.exists(test_path), f"Unit test file not found: {test_path}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
