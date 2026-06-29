A vulnerability has been found in Apache Druid version 0.20.0: the empty-key `""` bypass allows RCE via JavaScript.

Your fix approach: **Strict Input Validation at the Deserialization Layer**.

1. **Analyze the vulnerability** — identify that the empty string key `""` is used to smuggle `enabled: true` past the JavaScript security check.
2. **Locate the deserialization entry point** — find where `JavaScriptDimFilter` or the filter spec JSON is deserialized in `/root/druid/`.
3. **Implement input validation** — add a pre-deserialization check that:
   - Rejects any filter spec JSON containing an empty-string key `""`
   - Rejects `JavaScriptDimFilter` configurations where any dimension name is empty or `null`
   This validation must happen before the object is constructed.
4. **Create patch files** in `/root/patches/`.
5. **Apply patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
6. **Verify** the validation blocks the empty-key exploit while preserving normal requests.

Save all results to the expected output paths; use the field names defined by the task specification.