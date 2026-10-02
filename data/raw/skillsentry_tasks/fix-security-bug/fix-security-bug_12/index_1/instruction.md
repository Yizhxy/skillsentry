This is a security remediation task for a documented vulnerability in Apache Druid. The fix has to satisfy both negative tests (exploit blocked) and positive tests (legitimate requests succeed). Adhere to the jackson-security skill's prescribed workflow: analyse, locate, validate, patch, rebuild, verify.

A vulnerability has been discovered in Apache Druid version 0.20.0: authenticated attackers are able to run arbitrary code on the server by means of malicious JavaScript payloads.

The exploit relies on an empty key `""` in the filter configuration to circumvent JavaScript security settings:

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

Resolve the vulnerability AND author a JUnit unit test that confirms the patch stops the exploit.

**Fix approach:** Modify the source code AND author a unit test.
1. Create patch files in `/root/patches/` that stop the exploit.
2. Apply the patches to `/root/druid/`.
3. Author a JUnit test in `/root/druid/indexing-service/src/test/java/org/apache/druid/indexing/common/task/TestJavaScriptSecurityPatch.java` that:
   - Submits a mock request with the empty-key JavaScript bypass
   - Confirms it is blocked (exception thrown or filtered)
4. Rebuild using the command below.

Build command (skip web-console to prevent OOM, skip code quality checks for patched files):
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```

The verifier will deploy the patched JAR and restart Druid prior to running tests.
**IMPORTANT: Your fix must stop all such exploit requests while making sure that legitimate requests keep working correctly.**

You must use Apache Druid version 0.20.0.
