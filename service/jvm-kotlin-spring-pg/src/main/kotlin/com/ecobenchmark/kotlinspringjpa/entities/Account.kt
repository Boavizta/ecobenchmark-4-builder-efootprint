package com.ecobenchmark.kotlinspringjpa.entities

import jakarta.persistence.GenerationType
import java.time.Instant
import java.util.*
import jakarta.persistence.Entity
import jakarta.persistence.GeneratedValue
import jakarta.persistence.Id
import jakarta.persistence.OneToMany

@Entity
data class Account(
    var login: String,
    var creationDate: Instant,
    @OneToMany(mappedBy = "account")
    var lists: List<ListEntity>
) {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    var id: UUID? = null
}
