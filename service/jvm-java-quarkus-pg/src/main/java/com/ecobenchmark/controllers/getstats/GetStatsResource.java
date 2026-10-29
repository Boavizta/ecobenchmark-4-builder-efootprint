package com.ecobenchmark.controllers.getstats;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.persistence.EntityManager;
import jakarta.persistence.Query;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import java.util.List;

@Path("/api/stats")
@ApplicationScoped
@Produces("application/json")
public class GetStatsResource {

    @Inject
    private EntityManager entityManager;

    @GET
    public List<StatsResponse> getStats(){
        Query nativeQuery = entityManager.createNativeQuery("""
            SELECT
                id,
                login,
                count(list_id) AS nb_list,
                avg(nb_tasks) AS avg_tasks
            FROM (
                SELECT
                    account.id,
                    account.login,
                    list.id as list_id,
                    count(task.id) as nb_tasks
                FROM account
                INNER JOIN list ON (list.account_id=account.id)
                LEFT JOIN task ON (task.list_id=list.id)
                GROUP BY account.id, account.login, list.id
            ) t
            GROUP BY id, login""".trim(), "StatsResponseMapping");

        return nativeQuery.getResultList();

    }
}
