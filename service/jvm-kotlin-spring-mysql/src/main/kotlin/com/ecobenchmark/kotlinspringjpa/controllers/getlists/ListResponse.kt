package com.ecobenchmark.kotlinspringjpa.controllers.getlists

import java.time.Instant
import java.util.UUID
import com.fasterxml.jackson.annotation.JsonProperty

data class ListResponse(
    val id: UUID,
    val name: String,
    val tasks: MutableList<TaskResponse>,
    @get:JsonProperty("creation_date") val creationDate: Instant,
    @get:JsonProperty("account_id") val accountId: UUID
)
