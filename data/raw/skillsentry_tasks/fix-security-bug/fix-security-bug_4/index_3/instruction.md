A vulnerability has been found in Apache Druid version 0.20.0: the empty-key `""` bypass allows arbitrary JavaScript RCE.

Your fix approach: **JavaScript Sandboxing**.

First, **Analyze the vulnerability** — understand how the empty key bypasses the `druid.javascript.enabled` check and allows `Runtime.exec()`. Then **Locate the JavaScript evaluation entry point** — find where Druid evaluates JavaScript filter functions in the source. Next, **Implement a sandbox** — create a restricted script execution context that blocks access to dangerous Java classes (`java.lang.Runtime`, `ProcessBuilder`, `java.lang.System`, `Class.forName`). Wrap the existing JavaScript evaluation with this sandbox. Also add pre-deserialization validation to reject the empty-key pattern. After that, **Create patch files** in `/root/patches/`. Subsequently, **Apply patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```. Finally, **Verify** the sandbox blocks `Runtime.exec()` while legitimate JS filters still work.