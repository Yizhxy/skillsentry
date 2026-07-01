A vulnerability has been found in Apache Druid version 0.20.0: the empty-key `""` bypass allows `Runtime.exec()` via JavaScript.

Your fix approach: **Deny-list of dangerous Java class patterns**.

First, **Analyze the vulnerability** — identify that the JavaScript function body can reference `java.lang.Runtime`, `ProcessBuilder`, etc. Then **Locate the JavaScript evaluation entry point** in `/root/druid/` source. Next, **Implement a deny-list** — before executing any JavaScript function, scan the function body string for dangerous patterns:
   `java.lang.Runtime`, `ProcessBuilder`, `java.lang.System`, `Class.forName`, `exec(`, `getRuntime()`
   If any pattern matches, reject the request. Also add pre-deserialization validation for the empty-key `""` bypass. After that, **Create patch files** in `/root/patches/`. Subsequently, **Apply patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```. Finally, **Verify** the deny-list blocks dangerous patterns while allowing safe JavaScript filters.