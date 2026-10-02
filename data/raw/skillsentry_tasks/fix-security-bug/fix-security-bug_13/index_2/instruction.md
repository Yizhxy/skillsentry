Patch a known security vulnerability in Apache Druid. The fix must pass both negative tests (exploit blocked) and positive tests (legitimate requests succeed). Use the jackson-security skill's prescribed workflow: analyse, locate, validate, patch, rebuild, verify.

Vulnerability in Apache Druid version 0.20.0: the empty-key `""` in JavaScript filter configs allows RCE.

Fix approach: **HTTP-layer interception via a Servlet Filter**.

1. **Analyze the vulnerability** — the empty-key `""` bypass mechanism in the sampler API.
2. **Locate the entry point** — where `/druid/indexer/v1/sampler` requests are handled in the source.
3. **Implement a servlet filter** — a `javax.servlet.Filter` (or `Filter` from the appropriate package) intercepting requests to the sampler endpoint and rejecting bodies containing the `""` empty-key JavaScript bypass pattern. Register it for `/druid/indexer/v1/sampler`.
4. **Create patch files** in `/root/patches/` for all modified files.
5. **Apply patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
6. **Verify** exploit requests are blocked and legitimate ones allowed.
