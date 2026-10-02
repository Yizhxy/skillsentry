A security flaw has been discovered in Apache Druid version 0.20.0: authenticated attackers are able to run arbitrary code on the server by way of malicious JavaScript payloads, for instance:

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
The empty key `""` can circumvent JavaScript security settings and permit arbitrary code execution.

You are expected to:
1. Produce patch files that resolve this vulnerability in `/root/patches/`
2. Apply your patches to the Druid source code (a git repository) located at `/root/druid/`
3. Rebuild Druid with the fixes via Maven (skip web-console to prevent OOM error, skip code quality checks for patched files):
   ```bash
   cd /root/druid
   mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
   ```

The verifier will deploy the patched JAR to `/opt/druid/lib/` and restart the Druid server prior to running tests.
**IMPORTANT:Your patch must stop all such exploit requests while making sure that legitimate requests keep working properly.** The verifier contains relevant test cases to confirm both security and functionality.

You must operate on Apache Druid version 0.20.0.
