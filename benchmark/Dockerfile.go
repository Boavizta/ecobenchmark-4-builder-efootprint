# Native builds on both ARM64 and AMD64; no emulation in measurement runs.
FROM golang:1.24-bookworm AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -o /app .
FROM scratch
COPY --from=build /app /app
ENTRYPOINT ["/app"]
