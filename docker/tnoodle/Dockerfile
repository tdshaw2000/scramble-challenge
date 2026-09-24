FROM eclipse-temurin:21-jre-jammy

ARG TNOODLE_VERSION=1.2.3

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -L -o tnoodle.jar \
       "https://github.com/thewca/tnoodle/releases/download/v${TNOODLE_VERSION}/TNoodle-WCA-${TNOODLE_VERSION}.jar" \
    && apt-get purge -y curl && rm -rf /var/lib/apt/lists/*

EXPOSE 2014

CMD ["java", "-jar", "tnoodle.jar", "--nobrowser", "--noiconbar"]
