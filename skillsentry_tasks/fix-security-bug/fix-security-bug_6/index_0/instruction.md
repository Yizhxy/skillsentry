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

**Variant: Fix + Security Audit**

Fix the vulnerability AND perform a broader security audit: identify and list any other JavaScript-related endpoints in Druid that might have similar issues.

**Fix approach:** Patch the vulnerability AND audit for similar issues.
1. Write and apply a patch to block the empty-key JavaScript bypass.
2. Perform a code audit: search the Druid source for all endpoints that accept JavaScript (grep for `javascript`, `JavaScriptDimFilter`, `JavaScriptAggregator`, etc.).
3. Write a report at `/root/patches/security_audit.md` listing all JavaScript-related endpoints found.
4. Rebuild.

Build command (skip web-console to avoid OOM, skip code quality checks for patched files):
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```

The verifier will deploy the patched JAR and restart Druid before running tests.
**IMPORTANT: Your fix must block all such exploit requests while ensuring that legitimate requests continue to function correctly.**

You must work with Apache Druid version 0.20.0.