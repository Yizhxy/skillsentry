Under the `/workspace/` folder, there is a legacy user management microservice to migrate from Java 8/Spring Boot 2.7 to **Java 17/Spring Boot 3.2**.

Your migration should:

First, analyze current project structure — read pom.xml, identify all dependencies. Then upgrade Java version from 8 to **17** in pom.xml. Next, upgrade Spring Boot from 2.7.x to **3.2.x**. After that, migrate `javax.*` namespace to `jakarta.*` in all Java source files. Subsequently, update all dependency versions for compatibility with Spring Boot 3.2 + Java 17. Finally, migrate to Hibernate 6 — update entity mappings as needed. Lastly, update Spring Security 6 — replace deprecated `WebSecurityConfigurerAdapter`. Keep `RestTemplate` as-is (do **not** migrate to RestClient). Add a `@Deprecated` annotation to any RestTemplate bean and a comment explaining it should be migrated in a future sprint. Verify `RestTemplate` still compiles and functions under Spring Boot 3.2. Run `mvn clean compile` — must succeed. Run `mvn test` — all unit tests must pass

**Target: Java 17 / Spring Boot 3.2**