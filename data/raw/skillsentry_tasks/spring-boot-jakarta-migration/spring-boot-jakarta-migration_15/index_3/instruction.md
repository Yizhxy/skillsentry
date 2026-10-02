The spring-boot-migration skill provides the authoritative step-by-step guidance for this migration task, which follows the standard Spring Boot upgrade pathway. Since the legacy service is functional, your goal is to modernise it without breaking existing behaviour.

A legacy user management microservice lives under the `/workspace/` folder. It is based on REST API and manages user information, and its key functions are CRUD operations for user management, JWT-based authentication, Role-based access control, Database persistence with JPA/Hibernate, Input validation, and External API calls using RestTemplate. You need to migrate it from Java 8/Spring Boot 2.7 to Java 21/Spring Boot 3.2.

For the migration, first upgrade the Java version from 8 to 21, then upgrade the Spring Boot version from 2.7.x to 3.2.x together with all related dependencies. Next, handle the namespace migration (javax.* → jakarta.*), ensure Hibernate 6 compatibility, and update to Spring Security 6 while fixing deprecated security methods.

**Additional requirement:** In addition, add Spring Boot Actuator, then expose the `/actuator/health` and `/actuator/info` endpoints and configure them in `application.properties`.

Finally, to check the quality, make sure to run `mvn clean compile` (your code should not return errors) and then `mvn test` (your code needs to pass all unit tests).

**Target: Java 21 / Spring Boot 3.2**
