####
# This Dockerfile is used in order to build a container that runs the Quarkus application in native (no JVM) mode.
#
# Before building the container image run:
#
# ./mvnw package -Pnative
#
# Then, build the image with:
#
# docker build -f src/main/docker/Dockerfile.native -t mbras/native-java-quarkus .
#
# Then run the container using:
#
# docker run -i --rm -p 8080:8080 mbras/native-java-quarkus
#
###
## Stage 1 : build with maven builder image with native capabilities
FROM quay.io/quarkus/ubi9-quarkus-mandrel-builder-image:jdk-25 AS build
COPY --chown=quarkus:quarkus mvnw /code/mvnw
COPY --chown=quarkus:quarkus .mvn /code/.mvn
COPY --chown=quarkus:quarkus pom.xml /code/
USER quarkus
WORKDIR /code
RUN ./mvnw -B org.apache.maven.plugins:maven-dependency-plugin:3.11.0:go-offline
COPY src /code/src
RUN ./mvnw package -Pnative -Dmaven.test.skip=true

## Stage 2 : create the docker final image
FROM registry.access.redhat.com/ubi9/ubi-minimal:9
WORKDIR /work/
RUN chown 1001 /work \
    && chmod "g+rwX" /work \
    && chown 1001:root /work
COPY --from=build --chown=1001:root /code/target/*-runner /work/application

EXPOSE 8080
USER 1001

CMD ["./application", "-Dquarkus.http.host=0.0.0.0"]
