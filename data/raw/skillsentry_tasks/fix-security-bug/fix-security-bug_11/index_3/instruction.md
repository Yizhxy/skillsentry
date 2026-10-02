This is a security patching task for a known vulnerability in Apache Druid. The fix must pass both negative tests (exploit blocked) and positive tests (legitimate requests succeed). Follow the jackson-security skill's prescribed workflow: analyse, locate, validate, patch, rebuild, verify.

A vulnerability has been found in Apache Druid version 0.20.0: authenticated attackers can execute arbitrary code via the empty-key `""` JavaScript bypass.

Your task is to apply a **defense-in-depth** fix. First, **analyze the vulnerability** by identifying the empty key `""` attack vector in the JavaScript filter deserialization path. Then **locate the deserialization entry point**, finding the source files in `/root/druid/` where `JavaScriptDimFilter` or the sampler endpoint processes the incoming JSON. Next, **implement pre-deserialization validation**: add a validation step that detects and rejects requests containing the empty-key bypass pattern before any JavaScript evaluation occurs. After that, **create patch files** in `/root/patches/` documenting the changes, and **apply the patches and rebuild** with:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
Finally, **verify** that the fix blocks exploit payloads while preserving legitimate requests.

In addition, disable JavaScript globally in the Druid config (`druid.javascript.enabled=false`) as a second layer of defense.

**IMPORTANT: Both the source-level patch AND the config change are required. Config alone is insufficient.**
