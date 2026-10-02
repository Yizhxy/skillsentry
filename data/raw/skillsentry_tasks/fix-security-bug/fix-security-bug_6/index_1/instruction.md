A security flaw has been discovered in Apache Druid version 0.20.0: authenticated attackers are able to run arbitrary code on the server by means of malicious JavaScript payloads.

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

**Variant: Fix + Security Audit**

Resolve the vulnerability AND carry out a wider security audit: find and enumerate any other JavaScript-related endpoints in Druid that could have similar issues.

**Fix approach:** Patch the vulnerability AND audit for similar issues.
1. Author and apply a patch to stop the empty-key JavaScript bypass.
2. Carry out a code audit: search the Druid source for all endpoints that accept JavaScript (grep for `javascript`, `JavaScriptDimFilter`, `JavaScriptAggregator`, etc.).
3. Produce a report at `/root/patches/security_audit.md` enumerating all JavaScript-related endpoints found.
4. Rebuild.

Build command (skip web-console to prevent OOM, skip code quality checks for patched files):
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```

The verifier will deploy the patched JAR and restart Druid prior to running tests.
**IMPORTANT: Your fix must stop all such exploit requests while making sure that legitimate requests keep working correctly.**

You must operate on Apache Druid version 0.20.0.
