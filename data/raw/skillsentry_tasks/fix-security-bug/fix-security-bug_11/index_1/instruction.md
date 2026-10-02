This is a security remediation task for a documented vulnerability in Apache Druid. The fix has to satisfy both negative tests (exploit blocked) and positive tests (legitimate requests succeed). Adhere to the jackson-security skill's prescribed workflow: analyse, locate, validate, patch, rebuild, verify.

A vulnerability has been discovered in Apache Druid version 0.20.0: authenticated attackers are able to run arbitrary code through the empty-key `""` JavaScript bypass.

Your job is to put in place a **defense-in-depth** fix:

1. **Examine the vulnerability** — pinpoint the empty key `""` attack vector in the JavaScript filter deserialization path.
2. **Find the deserialization entry point** — track down the source files in `/root/druid/` where `JavaScriptDimFilter` or the sampler endpoint handles the incoming JSON.
3. **Add pre-deserialization validation** — introduce a validation step that spots and refuses requests containing the empty-key bypass pattern before any JavaScript evaluation takes place.
4. **Produce patch files** in `/root/patches/` recording the changes.
5. **Apply patches and rebuild** using:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
6. **Confirm** the fix stops exploit payloads while keeping legitimate requests working.

Furthermore, turn off JavaScript globally in the Druid config (`druid.javascript.enabled=false`) as a second layer of defense.

**IMPORTANT: Both the source-level patch AND the config change are mandatory. Config alone is not enough.**
