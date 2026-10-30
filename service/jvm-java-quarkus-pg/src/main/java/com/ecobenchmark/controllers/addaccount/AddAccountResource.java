package com.ecobenchmark.controllers.addaccount;

import com.ecobenchmark.entities.Account;
import com.ecobenchmark.repositories.AccountRepository;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.transaction.Transactional;
import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import java.time.Instant;

import static java.util.Collections.emptyList;

@Path("/api/accounts")
@ApplicationScoped
public class AddAccountResource {

    @Inject
    private AccountRepository accountRepository;

    @POST
    @Produces(MediaType.APPLICATION_JSON)
    @Consumes(MediaType.APPLICATION_JSON)
    @Transactional
    public AccountResponse addAccount(AccountRequest accountRequest) {
        Account account = new Account(accountRequest.getLogin(), Instant.now(), emptyList());
        accountRepository.persist(account);

        return new AccountResponse(account.getId(), account.getLogin(), account.getCreationDate());
    }
}
