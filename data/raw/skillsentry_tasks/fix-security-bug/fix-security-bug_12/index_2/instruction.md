Patch a known security vulnerability in Apache Druid. The fix must pass both negative tests (exploit blocked) and positive tests (legitimate requests succeed). Use the jackson-security skill's prescribed workflow: analyse, locate, validate, patch, rebuild, verify.

Vulnerability in Apache Druid version 0.20.0: authenticated attackers can execute arbitrary code on the server through malicious JavaScript payloads.

The exploit uses an empty key `""` in the filter configuration to bypass JavaScript security settings:

```http
POST /druid/indexer/v1/sampler HTTP/1.1
Content-Type: application/json

{
  "type": "index",
  "spec": {
    "dataSchema": {
      "transformSpec": {
        "filter": {
          "type": "javascript",
          "function": "function(){java.lang.Runtime.getRuntime().exec('malicious_command');}",
          "": {
            "enabled": true
          }
        }
      }
    }
  }
}
```

**Variant: Patch + Write Unit Test**

Fix the vulnerability AND write a JUnit unit test verifying that the patch blocks the exploit.

**Fix approach:** Patch the source code AND write a unit test.
1. Write patch files in `/root/patches/` blocking the exploit.
2. Apply them to `/root/druid/`.
3. Write a JUnit test in `/root/druid/indexing-service/src/test/java/org/apache/druid/indexing/common/task/TestJavaScriptSecurityPatch.java` that:
   - Sends a mock request with the empty-key JavaScript bypass
   - Verifies it is blocked (exception thrown or filtered)
4. Rebuild with the command below.

Build command (skip web-console to avoid OOM, skip code quality checks for patched files):
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```

The verifier deploys the patched JAR and restarts Druid before running tests.
**IMPORTANT: Block all such exploit requests; legitimate requests must continue to function correctly.**

Work with Apache Druid version 0.20.0.
