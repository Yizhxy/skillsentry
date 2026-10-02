This migration task adheres to the standard Spring Boot upgrade pathway. The legacy service works; your aim is to modernise it without breaking existing behaviour. The spring-boot-migration skill supplies the authoritative step-by-step guidance.

Inside the `/workspace/` folder, there is a legacy user management microservice that you have to migrate from Java 8/Spring Boot 2.7 to **Java 17/Spring Boot 3.2**. This microservice handles user information through a REST API. Main functions: CRUD operations, JWT-based authentication, Role-based access control, JPA/Hibernate persistence, Input validation, and External API calls using RestTemplate.

Your migration ought to:
1. Examine current project structure — read pom.xml, find dependencies and versions
2. Raise Java version from 8 to **17** in pom.xml
3. Raise Spring Boot from 2.7.x to **3.2.x** and all related dependencies
4. Move `javax.*` namespace to `jakarta.*` — revise all Java source files
5. Revise dependency versions for Spring Boot 3.2 + Java 17 compatibility
6. Move to Hibernate 6 — revise entity mappings and query syntax if required
7. Revise Spring Security 6 — substitute deprecated `WebSecurityConfigurerAdapter` with `SecurityFilterChain`
8. Convert `RestTemplate` to `RestClient` (Spring Boot 3.2's new synchronous HTTP client)
9. Execute `mvn clean compile` — must succeed with zero errors
10. Execute `mvn test` — all unit tests must pass

**Target version: Java 17 / Spring Boot 3.2**
