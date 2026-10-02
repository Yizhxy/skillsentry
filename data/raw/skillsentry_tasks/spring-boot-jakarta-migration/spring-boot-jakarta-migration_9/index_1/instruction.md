This migration task follows the conventional Spring Boot upgrade route. The legacy service works; your aim is to modernise it without breaking existing behaviour. The spring-boot-migration skill supplies the authoritative step-by-step guidance.

Inside the `/workspace/` folder, there is a legacy user management microservice that you have to port from Java 8/Spring Boot 2.7 to Java 21/Spring Boot 3.2. This microservice is built on REST API and handles user information. Main functions are: CRUD operations for user management, JWT-based authentication, Role-based access control, Database persistence with JPA/Hibernate, Input validation, and External API calls using RestTemplate.

Your migration should:
- Bump Java version from 8 to 21
- Bump Spring Boot version from 2.7.x to 3.2.x and all related dependencies
- Take care of namespace migration (javax.* → jakarta.*)
- Guarantee Hibernate 6 compatibility
- Move to Spring Security 6, repair deprecated security methods
- 

**Additional requirement:** Introduce Spring Cache with Caffeine implementation. Mark at least one service method with `@Cacheable`.

Be sure to execute the following commands to verify the quality:

1. `mvn clean compile` (your code should not return errors)
2. `mvn test` (your code needs to pass all unit tests)

**Target: Java 21 / Spring Boot 3.2**
