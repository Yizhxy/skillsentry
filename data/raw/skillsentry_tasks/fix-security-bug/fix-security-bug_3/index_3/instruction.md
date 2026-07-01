A vulnerability has been found in Apache Druid version 0.20.0: the empty-key `""` in JavaScript filter configs allows RCE.

Your fix approach: **HTTP-layer interception via a Servlet Filter**.

First, **Analyze the vulnerability** — understand the empty-key `""` bypass mechanism in the sampler API. Then **Locate the entry point** — find where `/druid/indexer/v1/sampler` requests are handled in the source. Next, **Implement a servlet filter** — add a `javax.servlet.Filter` (or `Filter` from the appropriate package) that intercepts requests to the sampler endpoint and rejects bodies containing the `""` empty-key JavaScript bypass pattern. Register it for `/druid/indexer/v1/sampler`. After that, **Create patch files** in `/root/patches/` for all modified files. Subsequently, **Apply patches and rebuild**:
```bash
cd /root/druid
mvn clean package -DskipTests -Dcheckstyle.skip=true -Dpmd.skip=true -Dforbiddenapis.skip=true -Dspotbugs.skip=true -Danimal.sniffer.skip=true -Denforcer.skip=true -Djacoco.skip=true -Ddependency-check.skip=true -pl '!web-console' -pl indexing-service -am
```. Finally, **Verify** the filter blocks exploit requests while allowing legitimate ones.