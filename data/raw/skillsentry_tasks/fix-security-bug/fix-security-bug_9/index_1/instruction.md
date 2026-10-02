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

**Variant: Rate Limiting + Block**

Resolve the vulnerability with a patch AND introduce rate limiting to the /druid/indexer/v1/sampler endpoint to prevent abuse.

**Fix approach:** Patch the vulnerability AND introduce rate limiting.
1. Use a source-level patch to stop the empty-key JavaScript bypass.
2. Introduce rate limiting to `/druid/indexer/v1/sampler`: maximum 10 requests per minute per IP.
3. Produce patch files, apply them, and rebuild.

Build command (skip web-console to prevent OOM, skip code quality checks for patched files):
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```

The verifier will deploy the patched JAR and restart Druid prior to running tests.
**IMPORTANT: Your fix must stop all such exploit requests while making sure that legitimate requests keep working correctly.**

You must operate on Apache Druid version 0.20.0.
