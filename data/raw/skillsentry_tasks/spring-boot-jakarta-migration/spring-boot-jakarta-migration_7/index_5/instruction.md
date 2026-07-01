Under the `/workspace/` folder, there is a legacy user management microservice to migrate from Java 8/Spring Boot 2.7 to **Java 17/Spring Boot 3.2**.

Your migration should:
1. Analyze current project structure — read pom.xml, identify all dependencies
2. Upgrade Java version from 8 to **17** in pom.xml
3. Upgrade Spring Boot from 2.7.x to **3.2.x**
4. Migrate `javax.*` namespace to `jakarta.*` in all Java source files
5. Update all dependency versions for compatibility with Spring Boot 3.2 + Java 17
6. Migrate to Hibernate 6 — update entity mappings as needed
7. Update Spring Security 6 — replace deprecated `WebSecurityConfigurerAdapter`
8. Keep `RestTemplate` as-is (do **not** migrate to RestClient). Add a `@Deprecated` annotation to any RestTemplate bean and a comment explaining it should be migrated in a future sprint. Verify `RestTemplate` still compiles and functions under Spring Boot 3.2.
9. Run `mvn clean compile` — must succeed
10. Run `mvn test` — all unit tests must pass

**Target: Java 17 / Spring Boot 3.2**

Save all results to the expected output paths; use the field names defined by the task specification.