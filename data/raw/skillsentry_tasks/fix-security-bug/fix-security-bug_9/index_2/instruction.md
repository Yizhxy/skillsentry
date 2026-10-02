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

**Variant: Rate Limiting + Block**

Fix the vulnerability with a patch AND add rate limiting to the /druid/indexer/v1/sampler endpoint to prevent abuse.

**Fix approach:** Patch the vulnerability AND add rate limiting.
1. Apply a source-level patch blocking the empty-key JavaScript bypass.
2. Rate-limit `/druid/indexer/v1/sampler`: maximum 10 requests per minute per IP.
3. Write patch files, apply, rebuild.

Build (skip web-console to avoid OOM, skip code quality checks for patched files):
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```

The verifier deploys the patched JAR and restarts Druid before running tests.
**IMPORTANT: Block all such exploit requests while keeping legitimate requests functioning correctly.**

Use Apache Druid version 0.20.0.
