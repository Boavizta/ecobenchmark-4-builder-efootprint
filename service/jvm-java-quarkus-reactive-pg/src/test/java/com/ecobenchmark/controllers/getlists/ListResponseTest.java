package com.ecobenchmark.controllers.getlists;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ListResponseTest {
    @Test
    void emptyListUsesApiFieldNames() throws Exception {
        UUID accountId = UUID.randomUUID();
        ListResponse response = new ListResponse(UUID.randomUUID(), "empty", Instant.now(), accountId);
        var json = new ObjectMapper().findAndRegisterModules().valueToTree(response);
        assertTrue(json.has("creation_date"));
        assertEquals(accountId.toString(), json.get("account_id").asText());
        assertEquals(0, json.get("tasks").size());
        assertFalse(json.has("creationDate"));
    }
}
