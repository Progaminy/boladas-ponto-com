# Migração do Boladas para Supabase PostgreSQL

O banco relacional de produção passa de SQLite para PostgreSQL no Supabase. O Backblaze B2 continua responsável por imagens, vídeos e artefactos de proveniência.

## Estado

- Projeto Supabase dedicado: `boladas-ponto-com`.
- Project ref: `ofrrbesgjdkstxisotbs`.
- Região: `eu-west-1`.
- Schema principal criado e protegido com RLS.
- `anon` e `authenticated` não têm privilégios nas tabelas do Boladas.
- Role de backend dedicada: `boladas_app`.
- SQLite continua disponível somente para desenvolvimento/testes quando `DATABASE_URL` não existe.

## Produção

O serviço FastAPI deve receber `DATABASE_URL` como segredo de implantação. Para um ambiente IPv4 como Render, usa a ligação **Session pooler** mostrada no painel **Connect** do projeto Supabase, na porta 5432, com a role `boladas_app`.

A aplicação não executa DDL no arranque PostgreSQL. Alterações de schema são feitas através de migrations do Supabase, permitindo que a role de runtime tenha somente privilégios de dados.

## Cópia de dados SQLite

Se existir um `data/posts.db` real de uma instalação anterior:

```bash
DATABASE_URL='postgresql://...' python scripts/migrate_sqlite_to_postgres.py --sqlite data/posts.db
```

O script pressupõe que o schema Supabase já foi migrado. Ele copia as tabelas em ordem de chaves estrangeiras, mantém IDs, usa inserções idempotentes e verifica as contagens antes do commit.

## Antes do merge/deploy

1. Definir uma password forte para `boladas_app` diretamente no Supabase, sem a colocar no Git.
2. Copiar do painel **Connect** a Session pooler URL e configurar `DATABASE_URL` no serviço Render.
3. Se existir SQLite de produção, executar a cópia de dados e conferir as contagens.
4. Fazer smoke test de `/health`, registo/login, feed, empresas, mensagens, comentários e publicação.
5. Só então retirar o PR de draft, fazer merge e deploy.
