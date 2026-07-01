A vulnerability has been found in Apache Druid version 0.20.0: the empty-key `""` bypass enables RCE.

Your fix approach: **Role-based allowlist for JavaScript execution**.

1. **Analyze the vulnerability** — understand the attack vector: authenticated users can bypass JS security via empty key.
2. **Locate the JavaScript evaluation entry point** in `/root/druid/` source.
3. **Implement allowlist gating** — modify the JavaScript evaluation path so that:
   - JavaScript execution is only permitted for requests with an admin/superuser role
   - All other requests that attempt JavaScript evaluation are rejected with HTTP 403
   - Also add pre-deserialization validation to reject the empty-key pattern regardless of role
4. **Create patch files** in `/root/patches/`.
5. **Apply patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
6. **Verify** the fix blocks unauthenticated/non-admin JavaScript execution and the empty-key exploit.