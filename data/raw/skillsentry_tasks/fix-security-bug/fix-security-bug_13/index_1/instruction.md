This is a security remediation task for a documented vulnerability in Apache Druid. The fix has to satisfy both negative tests (exploit blocked) and positive tests (legitimate requests succeed). Adhere to the jackson-security skill's prescribed workflow: analyse, locate, validate, patch, rebuild, verify.

A vulnerability has been discovered in Apache Druid version 0.20.0: the empty-key `""` in JavaScript filter configs permits RCE.

Your remediation strategy: **HTTP-layer interception via a Servlet Filter**.

1. **Examine the vulnerability** — grasp the empty-key `""` bypass mechanism in the sampler API.
2. **Find the entry point** — determine where `/druid/indexer/v1/sampler` requests are processed in the source.
3. **Build a servlet filter** — introduce a `javax.servlet.Filter` (or `Filter` from the appropriate package) that catches requests to the sampler endpoint and refuses bodies containing the `""` empty-key JavaScript bypass pattern. Register it for `/druid/indexer/v1/sampler`.
4. **Produce patch files** in `/root/patches/` for every modified file.
5. **Apply patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
6. **Confirm** the filter stops exploit requests while letting legitimate ones through.
