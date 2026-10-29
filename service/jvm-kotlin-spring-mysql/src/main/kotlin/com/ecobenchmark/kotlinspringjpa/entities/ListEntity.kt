package com.ecobenchmark.kotlinspringjpa.entities

import java.time.Instant
import java.util.*
import jakarta.persistence.*

@Entity(name = "list")
class ListEntity(
    @ManyToOne
    var account: Account,
    var name: String,
    var creationDate: Instant,
    @OneToMany(mappedBy = "list")
    var tasks: List<Task>
) {
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    var id: UUID? = null
}
