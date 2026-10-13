# api/

Entra na F2, junto com a tela de masterset. As rotas estão desenhadas em
[../docs/arquitetura.md](../docs/arquitetura.md) e a consulta que alimenta a
principal já existe e está testada: [`db/queries/masterset.sql`](../db/queries/masterset.sql).

Nada aqui consulta API externa durante um request. O app lê só o Postgres.
