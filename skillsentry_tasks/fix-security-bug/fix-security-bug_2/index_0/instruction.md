A vulnerability has been found in Apache Druid version 0.20.0: authenticated attackers can execute arbitrary code on the server through malicious JavaScript payloads.

```http
POST /druid/indexer/v1/sampler HTTP/1.1
Content-Type: application/json

The exploit uses an empty key `""` in the filter configuration to bypass JavaScript security settings:

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

Fix the vulnerability AND write a JUnit unit test that verifies the patch blocks the exploit.

**Fix approach:** Patch the source code AND write a unit test.
1. Write patch files in `/root/patches/` that block the exploit.
2. Apply the patches to `/root/druid/`.
3. Write a JUnit test in `/root/druid/indexing-service/src/test/java/org/apache/druid/indexing/common/task/TestJavaScriptSecurityPatch.java` that:
   - Sends a mock request with the empty-key JavaScript bypass
   - Verifies it is blocked (exception thrown or filtered)
4. Rebuild with the command below.

Build command (skip web-console to avoid OOM, skip code quality checks for patched files):
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```

The verifier will deploy the patched JAR and restart Druid before running tests.
**IMPORTANT: Your fix must block all such exploit requests while ensuring that legitimate requests continue to function correctly.**

You must work with Apache Druid version 0.20.0.