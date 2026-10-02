This is a security patching task for a known vulnerability in Apache Druid. The fix must pass both negative tests (exploit blocked) and positive tests (legitimate requests succeed). Follow the jackson-security skill's prescribed workflow: analyse, locate, validate, patch, rebuild, verify.

A vulnerability has been found in Apache Druid version 0.20.0: the empty-key `""` bypass allows RCE via JavaScript.

Your fix approach is **Strict Input Validation at the Deserialization Layer**. First, **analyze the vulnerability** and identify that the empty string key `""` is used to smuggle `enabled: true` past the JavaScript security check. Then **locate the deserialization entry point** by finding where `JavaScriptDimFilter` or the filter spec JSON is deserialized in `/root/druid/`. Next, **implement input validation**: add a pre-deserialization check that rejects any filter spec JSON containing an empty-string key `""` and rejects `JavaScriptDimFilter` configurations where any dimension name is empty or `null`; this validation must happen before the object is constructed. After that, **create patch files** in `/root/patches/`, then **apply the patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
Finally, **verify** that the validation blocks the empty-key exploit while preserving normal requests.
