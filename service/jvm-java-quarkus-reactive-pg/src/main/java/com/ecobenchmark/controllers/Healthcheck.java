package com.ecobenchmark.controllers;

import io.smallrye.mutiny.Uni;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.core.Response;

@Path("/healthcheck")
public class Healthcheck {

    @GET
    public Uni<Response> healthcheck() {
        return Uni.createFrom().item(Response.noContent().build());
    }
}
