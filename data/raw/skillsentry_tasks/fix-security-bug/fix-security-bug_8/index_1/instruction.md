A vulnerability has been found in Apache Druid version 0.20.0: the empty-key `""` bypass allows `Runtime.exec()` via JavaScript.

Your fix approach: **Deny-list of dangerous Java class patterns**.

1. **Analyze the vulnerability** — find that the JavaScript function body can reference `java.lang.Runtime`, `ProcessBuilder`, etc.
2. **Locate the JavaScript evaluation entry point** in `/root/druid/` source.
3. **write a deny-list** — before executing any JavaScript function, scan the function body string for dangerous patterns:
   `java.lang.Runtime`, `ProcessBuilder`, `java.lang.System`, `Class.forName`, `exec(`, `getRuntime()`
   If any pattern matches, reject the request. Also add pre-deserialization validation for the empty-key `""` bypass.
4. **Create patch files** in `/root/patches/`.
5. **use patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
6. **check** the deny-list blocks dangerous patterns while allowing safe JavaScript filters.
