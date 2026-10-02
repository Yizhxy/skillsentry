Follow the standard Spring Boot upgrade pathway for this migration. The legacy service is functional; modernise it without breaking existing behaviour. Use the spring-boot-migration skill for the authoritative step-by-step guidance.

Migrate the legacy user management microservice under the `/workspace/` folder from Java 8/Spring Boot 2.7 to **Java 17/Spring Boot 3.2**. It manages user information via REST API. Key functions: CRUD operations, JWT-based authentication, Role-based access control, JPA/Hibernate persistence, Input validation, and External API calls using RestTemplate.

Steps:
1. Analyze project structure — read pom.xml, identify dependencies and versions
2. Upgrade Java 8 → **17** in pom.xml
3. Upgrade Spring Boot 2.7.x → **3.2.x** with all related dependencies
4. Migrate `javax.*` → `jakarta.*` in all Java source files
5. Update dependency versions for Spring Boot 3.2 + Java 17 compatibility
6. Migrate to Hibernate 6; update entity mappings and query syntax if needed
7. Update Spring Security 6; replace deprecated `WebSecurityConfigurerAdapter` with `SecurityFilterChain`
8. Migrate `RestTemplate` to `RestClient` (Spring Boot 3.2's new synchronous HTTP client)
9. Run `mvn clean compile` — zero errors
10. Run `mvn test` — all unit tests pass

**Target: Java 17 / Spring Boot 3.2**
