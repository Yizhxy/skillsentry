Under the `/workspace/` folder, there is a legacy user management microservice that you need to migrate from Java 8/Spring Boot 2.7 to **Java 17/Spring Boot 3.2**. This microservice manages user information via REST API. Key functions: CRUD operations, JWT-based authentication, Role-based access control, JPA/Hibernate persistence, Input validation, and External API calls using RestTemplate.

**Target: Java 17 / Spring Boot 3.2**

Your migration should:
1. Analyze current project structure — read pom.xml, identify dependencies and versions
2. Upgrade Java version from 8 to **17** in pom.xml
3. Upgrade Spring Boot from 2.7.x to **3.2.x** and all related dependencies
4. Migrate `javax.*` namespace to `jakarta.*` — update all Java source files
5. Update dependency versions for Spring Boot 3.2 + Java 17 compatibility
6. Migrate to Hibernate 6 — update entity mappings and query syntax if needed
7. Update Spring Security 6 — replace deprecated `WebSecurityConfigurerAdapter` with `SecurityFilterChain`
8. Migrate `RestTemplate` to `RestClient` (Spring Boot 3.2's new synchronous HTTP client)
9. Run `mvn clean compile` — must succeed with zero errors
10. Run `mvn test` — all unit tests must pass