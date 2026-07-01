"""
Tests for Spring Boot migration task.
Target: Java 21 / Spring Boot 3.2
"""

import os
import subprocess
import pytest


def run_command(cmd, cwd="/workspace"):
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=300
    )
    return result


class TestSpringBootMigration:
    def test_workspace_exists(self):
        assert os.path.isdir("/workspace"), "Workspace directory not found"

    def test_pom_xml_exists(self):
        pom_path = "/workspace/pom.xml"
        assert os.path.exists(pom_path), "pom.xml not found"

    def test_spring_boot_version(self):
        pom_path = "/workspace/pom.xml"
        if os.path.exists(pom_path):
            with open(pom_path) as f:
                content = f.read()
            assert "3.2" in content, f"pom.xml should target Spring Boot 3.2"

    def test_java_version(self):
        pom_path = "/workspace/pom.xml"
        if os.path.exists(pom_path):
            with open(pom_path) as f:
                content = f.read()
            assert "21" in content, f"pom.xml should target Java 21"

    def test_jakarta_namespace_migration(self):
        """Verify javax imports were migrated to jakarta."""
        import_count = 0
        for root, _, files in os.walk("/workspace/src"):
            for fname in files:
                if fname.endswith(".java"):
                    with open(os.path.join(root, fname)) as f:
                        content = f.read()
                    if "import javax.persistence" in content or "import javax.validation" in content:
                        import_count += 1
        assert import_count == 0, f"Found {import_count} files still using javax.* imports (should be jakarta.*)"

    def test_mvn_compile(self):
        result = run_command("mvn clean compile -q 2>&1 | tail -5")
        assert result.returncode == 0, f"mvn compile failed:\n{result.stdout}\n{result.stderr}"

    def test_mvn_tests_pass(self):
        result = run_command("mvn test -q 2>&1 | tail -20")
        assert result.returncode == 0, f"mvn test failed:\n{result.stdout}\n{result.stderr}"

    def test_openapi_dependency(self):
        """Check springdoc-openapi dependency is present."""
        pom_path = "/workspace/pom.xml"
        if os.path.exists(pom_path):
            with open(pom_path) as f:
                content = f.read()
            assert "springdoc-openapi" in content, "pom.xml should include springdoc-openapi dependency"

