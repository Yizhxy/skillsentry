Follow the standard Spring Boot upgrade pathway for this migration. The legacy service is functional; modernise it without breaking existing behaviour. Use the spring-boot-migration skill for the authoritative step-by-step guidance.

Migrate the legacy user management microservice under the `/workspace/` folder from Java 8/Spring Boot 2.7 to Java 21/Spring Boot 3.2. It is a REST API service managing user information. Key functions: CRUD operations for user management, JWT-based authentication, Role-based access control, Database persistence with JPA/Hibernate, Input validation, and External API calls using RestTemplate.

Migration checklist:
- Upgrade Java from 8 to 21
- Upgrade Spring Boot from 2.7.x to 3.2.x plus all related dependencies
- Migrate namespaces (javax.* → jakarta.*)
- Ensure Hibernate 6 compatibility
- Update to Spring Security 6; fix deprecated security methods

**Additional requirement:** Integrate SpringDoc OpenAPI 3.0: include the `springdoc-openapi-starter-webmvc-ui` dependency and annotate at least the main REST endpoints with `@Operation` and `@ApiResponse`.

Run the following commands to check quality:

1. `mvn clean compile` — no errors
2. `mvn test` — all unit tests pass

**Target: Java 21 / Spring Boot 3.2**
