This is a security patching task for a known vulnerability in Apache Druid. The fix must pass both negative tests (exploit blocked) and positive tests (legitimate requests succeed). Follow the jackson-security skill's prescribed workflow: analyse, locate, validate, patch, rebuild, verify.

A vulnerability has been found in Apache Druid version 0.20.0: the empty-key `""` bypass allows arbitrary JavaScript RCE.

Your fix approach is **JavaScript Sandboxing**. First, **analyze the vulnerability** to understand how the empty key bypasses the `druid.javascript.enabled` check and allows `Runtime.exec()`. Then **locate the JavaScript evaluation entry point** by finding where Druid evaluates JavaScript filter functions in the source. Next, **implement a sandbox**: create a restricted script execution context that blocks access to dangerous Java classes (`java.lang.Runtime`, `ProcessBuilder`, `java.lang.System`, `Class.forName`), wrap the existing JavaScript evaluation with this sandbox, and also add pre-deserialization validation to reject the empty-key pattern. After that, **create patch files** in `/root/patches/`, then **apply the patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
Finally, **verify** that the sandbox blocks `Runtime.exec()` while legitimate JS filters still work.
