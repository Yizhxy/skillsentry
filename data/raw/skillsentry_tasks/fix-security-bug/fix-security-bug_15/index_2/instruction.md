Patch a known security vulnerability in Apache Druid. The fix must pass both negative tests (exploit blocked) and positive tests (legitimate requests succeed). Use the jackson-security skill's prescribed workflow: analyse, locate, validate, patch, rebuild, verify.

Vulnerability in Apache Druid version 0.20.0: the empty-key `""` bypass allows RCE via JavaScript.

Fix approach: **Strict Input Validation at the Deserialization Layer**.

1. **Analyze the vulnerability** — the empty string key `""` smuggles `enabled: true` past the JavaScript security check.
2. **Locate the deserialization entry point** — where `JavaScriptDimFilter` or the filter spec JSON is deserialized in `/root/druid/`.
3. **Implement input validation** — a pre-deserialization check that:
   - Rejects any filter spec JSON containing an empty-string key `""`
   - Rejects `JavaScriptDimFilter` configurations where any dimension name is empty or `null`
   Run this validation before the object is constructed.
4. **Create patch files** in `/root/patches/`.
5. **Apply patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
6. **Verify** the empty-key exploit is blocked and normal requests preserved.
