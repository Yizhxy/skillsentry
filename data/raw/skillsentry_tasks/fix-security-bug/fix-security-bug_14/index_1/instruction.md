This is a security remediation task for a documented vulnerability in Apache Druid. The fix has to satisfy both negative tests (exploit blocked) and positive tests (legitimate requests succeed). Adhere to the jackson-security skill's prescribed workflow: analyse, locate, validate, patch, rebuild, verify.

A vulnerability has been discovered in Apache Druid version 0.20.0: the empty-key `""` bypass permits arbitrary JavaScript RCE.

Your remediation strategy: **JavaScript Sandboxing**.

1. **Examine the vulnerability** — work out how the empty key gets around the `druid.javascript.enabled` check and permits `Runtime.exec()`.
2. **Find the JavaScript evaluation entry point** — determine where Druid runs JavaScript filter functions in the source.
3. **Build a sandbox** — set up a restricted script execution context that prevents access to dangerous Java classes (`java.lang.Runtime`, `ProcessBuilder`, `java.lang.System`, `Class.forName`). Enclose the existing JavaScript evaluation in this sandbox. In addition, introduce pre-deserialization validation to refuse the empty-key pattern.
4. **Produce patch files** in `/root/patches/`.
5. **Apply patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
6. **Confirm** the sandbox stops `Runtime.exec()` while legitimate JS filters keep working.
