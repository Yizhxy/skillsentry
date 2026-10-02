Vulnerability in Apache Druid version 0.20.0: the empty-key `""` bypass allows arbitrary JavaScript RCE.

Fix approach: **JavaScript Sandboxing**.

1. **Analyze the vulnerability** — understand how the empty key bypasses the `druid.javascript.enabled` check and allows `Runtime.exec()`.
2. **Locate the JavaScript evaluation entry point** — find where Druid evaluates JavaScript filter functions in the source.
3. **Implement a sandbox** — create a restricted script execution context blocking access to dangerous Java classes (`java.lang.Runtime`, `ProcessBuilder`, `java.lang.System`, `Class.forName`). Wrap the existing JavaScript evaluation with it. Also add pre-deserialization validation rejecting the empty-key pattern.
4. **Create patch files** in `/root/patches/`.
5. **Apply patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
6. **Verify** the sandbox blocks `Runtime.exec()` and legitimate JS filters still work.
