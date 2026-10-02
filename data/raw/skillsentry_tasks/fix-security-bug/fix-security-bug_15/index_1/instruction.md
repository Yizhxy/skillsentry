This is a security remediation task for a documented vulnerability in Apache Druid. The fix has to satisfy both negative tests (exploit blocked) and positive tests (legitimate requests succeed). Adhere to the jackson-security skill's prescribed workflow: analyse, locate, validate, patch, rebuild, verify.

A vulnerability has been discovered in Apache Druid version 0.20.0: the empty-key `""` bypass permits RCE through JavaScript.

Your remediation strategy: **Strict Input Validation at the Deserialization Layer**.

1. **Examine the vulnerability** — recognize that the empty string key `""` is exploited to sneak `enabled: true` past the JavaScript security check.
2. **Find the deserialization entry point** — determine where `JavaScriptDimFilter` or the filter spec JSON is deserialized in `/root/druid/`.
3. **Add input validation** — introduce a pre-deserialization check that:
   - Refuses any filter spec JSON containing an empty-string key `""`
   - Refuses `JavaScriptDimFilter` configurations where any dimension name is empty or `null`
   This validation must take place before the object is constructed.
4. **Produce patch files** in `/root/patches/`.
5. **Apply patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
6. **Confirm** the validation stops the empty-key exploit while keeping normal requests intact.
