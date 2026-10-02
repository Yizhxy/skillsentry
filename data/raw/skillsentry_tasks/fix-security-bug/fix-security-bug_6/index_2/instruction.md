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

**Variant: Fix + Security Audit**

Fix the vulnerability AND perform a broader security audit: identify and list any other JavaScript-related endpoints in Druid that might have similar issues.

**Fix approach:** Patch the vulnerability AND audit for similar issues.
1. Write and apply a patch blocking the empty-key JavaScript bypass.
2. Audit the code: search the Druid source for all endpoints that accept JavaScript (grep for `javascript`, `JavaScriptDimFilter`, `JavaScriptAggregator`, etc.).
3. Write a report at `/root/patches/security_audit.md` listing all JavaScript-related endpoints found.
4. Rebuild.

Build (skip web-console to avoid OOM, skip code quality checks for patched files):
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```

The verifier deploys the patched JAR and restarts Druid before running tests.
**IMPORTANT: Block all such exploit requests while keeping legitimate requests functioning correctly.**

Use Apache Druid version 0.20.0.
