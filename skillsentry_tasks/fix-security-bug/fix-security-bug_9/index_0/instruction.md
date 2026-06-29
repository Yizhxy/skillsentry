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

**Variant: Rate Limiting + Block**

Fix the vulnerability with a patch AND add rate limiting to the /druid/indexer/v1/sampler endpoint to prevent abuse.

**Fix approach:** Patch the vulnerability AND add rate limiting.
1. Apply a source-level patch to block the empty-key JavaScript bypass.
2. Add rate limiting to `/druid/indexer/v1/sampler`: maximum 10 requests per minute per IP.
3. Write patch files, apply, and rebuild.

Build command (skip web-console to avoid OOM, skip code quality checks for patched files):
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```

The verifier will deploy the patched JAR and restart Druid before running tests.
**IMPORTANT: Your fix must block all such exploit requests while ensuring that legitimate requests continue to function correctly.**

You must work with Apache Druid version 0.20.0.