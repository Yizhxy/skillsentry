"""Tests for spring-boot-jakarta-migration — Java 17 / Spring Boot 3.2, RestTemplate kept."""
import os, subprocess, pytest

def run_mvn(cmd, cwd="/workspace"):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=300)

class TestSpringMigration:
    def test_pom_exists(self):
        assert os.path.exists("/workspace/pom.xml")

    def test_spring_boot_version_32(self):
        with open("/workspace/pom.xml") as f: content = f.read()
        assert "3.2" in content, "pom.xml should target Spring Boot 3.2"

    def test_java_version_17(self):
        with open("/workspace/pom.xml") as f: content = f.read()
        assert "17" in content, "pom.xml should target Java 17"

    def test_jakarta_namespace(self):
        count = 0
        for root, _, files in os.walk("/workspace/src"):
            for fname in files:
                if fname.endswith(".java"):
                    with open(os.path.join(root, fname)) as f: c = f.read()
                    if "import javax.persistence" in c or "import javax.validation" in c:
                        count += 1
        assert count == 0, f"{count} files still use javax.* imports"

    def test_rest_template_retained(self):
        result = subprocess.run(
            ["grep", "-r", "RestTemplate", "--include=*.java", "-l"],
            capture_output=True, text=True, cwd="/workspace/src"
        )
        assert len(result.stdout.strip()) > 0, "RestTemplate should still be present"

    def test_mvn_compile(self):
        r = run_mvn("mvn clean compile -q 2>&1 | tail -5")
        assert r.returncode == 0, f"Compile failed:\n{r.stdout}\n{r.stderr}"

    def test_mvn_tests(self):
        r = run_mvn("mvn test -q 2>&1 | tail -20")
        assert r.returncode == 0, f"Tests failed:\n{r.stdout}\n{r.stderr}"
