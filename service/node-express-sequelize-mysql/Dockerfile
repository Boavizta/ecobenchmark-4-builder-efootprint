FROM node:26-bookworm-slim

ENV PORT=8080

WORKDIR /code
COPY package.json package-lock.json /code/
RUN npm clean-install

COPY src /code/src

ENTRYPOINT ["/usr/local/bin/node", "/code/src/main.js"]
