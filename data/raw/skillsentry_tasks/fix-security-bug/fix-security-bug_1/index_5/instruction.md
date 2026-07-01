A vulnerability has been found in Apache Druid version 0.20.0: authenticated attackers can execute arbitrary code via the empty-key `""` JavaScript bypass.

Your task is to apply a **defense-in-depth** fix:

1. **Analyze the vulnerability** — identify the empty key `""` attack vector in the JavaScript filter deserialization path.
2. **Locate the deserialization entry point** — find the source files in `/root/druid/` where `JavaScriptDimFilter` or the sampler endpoint processes the incoming JSON.
3. **Implement pre-deserialization validation** — add a validation step that detects and rejects requests containing the empty-key bypass pattern before any JavaScript evaluation occurs.
4. **Create patch files** in `/root/patches/` documenting the changes.
5. **Apply patches and rebuild** with:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
6. **Verify** the fix blocks exploit payloads while preserving legitimate requests.

Additionally, disable JavaScript globally in the Druid config (`druid.javascript.enabled=false`) as a second layer of defense.

**IMPORTANT: Both the source-level patch AND the config change are required. Config alone is insufficient.**

Save all results to the expected output paths; use the field names defined by the task specification.