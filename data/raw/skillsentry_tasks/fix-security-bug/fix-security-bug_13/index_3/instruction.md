This is a security patching task for a known vulnerability in Apache Druid. The fix must pass both negative tests (exploit blocked) and positive tests (legitimate requests succeed). Follow the jackson-security skill's prescribed workflow: analyse, locate, validate, patch, rebuild, verify.

A vulnerability has been found in Apache Druid version 0.20.0: the empty-key `""` in JavaScript filter configs allows RCE.

Your fix approach is **HTTP-layer interception via a Servlet Filter**. First, **analyze the vulnerability** to understand the empty-key `""` bypass mechanism in the sampler API. Then **locate the entry point** by finding where `/druid/indexer/v1/sampler` requests are handled in the source. Next, **implement a servlet filter**: add a `javax.servlet.Filter` (or `Filter` from the appropriate package) that intercepts requests to the sampler endpoint and rejects bodies containing the `""` empty-key JavaScript bypass pattern, and register it for `/druid/indexer/v1/sampler`. After that, **create patch files** in `/root/patches/` for all modified files, then **apply the patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```
Finally, **verify** that the filter blocks exploit requests while allowing legitimate ones.
