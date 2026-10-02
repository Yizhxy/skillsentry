This migration task adheres to the standard Spring Boot upgrade pathway. The legacy service works; your aim is to modernise it without breaking existing behaviour. The spring-boot-migration skill supplies the authoritative step-by-step guidance.

Inside the `/workspace/` folder, there is a legacy user management microservice that you have to migrate from Java 8/Spring Boot 2.7 to Java 21/Spring Boot 3.2. This microservice is built on REST API and handles user information. Main functions are: CRUD operations for user management, JWT-based authentication, Role-based access control, Database persistence with JPA/Hibernate, Input validation, and External API calls using RestTemplate.

Your migration ought to:
- Raise the Java version from 8 to 21
- Raise the Spring Boot version from 2.7.x to 3.2.x along with all related dependencies
- Take care of namespace migration (javax.* → jakarta.*)
- Guarantee Hibernate 6 compatibility
- Move to Spring Security 6, repair deprecated security methods
- Convert `RestTemplate` to `WebClient` (reactive, from spring-webflux) for non-blocking HTTP calls.

Be sure to execute the following commands to verify the quality:

1. `mvn clean compile` (your code must not produce errors)
2. `mvn test` (your code has to pass all unit tests)

**Target version: Java 21 / Spring Boot 3.2**
