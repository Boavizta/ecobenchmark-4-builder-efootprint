package com.ecobenchmark.controllers.addaccount;

import com.ecobenchmark.entities.Account;
import com.ecobenchmark.repositories.AccountRepository;
import io.quarkus.hibernate.reactive.panache.common.WithTransaction;
import io.smallrye.mutiny.Uni;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
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
    AccountRepository accountRepository;

    @POST
    @Produces(MediaType.APPLICATION_JSON)
    @Consumes(MediaType.APPLICATION_JSON)
    @WithTransaction
    public Uni<AccountResponse> addAccount(AccountRequest accountRequest) {
        Account account = new Account(accountRequest.getLogin(), Instant.now(), emptyList());
        return accountRepository.persist(account).onItem().transform(this::getAccountResponse);
    }

    private AccountResponse getAccountResponse(Account newAccount) {
        return new AccountResponse(newAccount.getId(), newAccount.getLogin(), newAccount.getCreationDate());
    }
}
