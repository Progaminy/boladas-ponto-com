# Boladas-ponto-com

**Do zero ao infinito.**

Boladas-ponto-com é um mercado digital para particulares, lojas e empresas publicarem produtos e serviços e entrarem em contacto direto com compradores.

## Como funciona

- O vendedor cria a conta e pode registar uma ou várias empresas.
- O anúncio é escrito pelo próprio vendedor.
- Cada produto deve ter 1 ou 2 fotos reais; a primeira é a foto principal.
- O feed público permite procurar anúncios por categoria e localização.
- O comparador ajuda a comparar preços e distância quando existe localização disponível.
- Compradores e vendedores podem conversar pelo Messenger Boladas.
- O vendedor pode pausar ou marcar o produto como vendido.
- Utilizadores podem gostar, não gostar, comentar e reportar anúncios.
- A equipa da plataforma pode fazer revisão humana e prestar apoio de mediação.

## Arquitetura

- **Backend:** FastAPI + Jinja2
- **Base de dados de produção:** PostgreSQL / Supabase através de `DATABASE_URL`
- **Desenvolvimento local:** SQLite quando `DATABASE_URL` não está definida
- **Fotos e vídeos:** Backblaze B2 pela API S3 compatível
- **Autenticação:** bcrypt + cookie de sessão assinado
- **Deploy:** Render

## Publicação

A publicação é direta. Não existe etapa de geração de conteúdo. O servidor valida os campos, aplica regras locais de moderação, grava o anúncio no banco e recebe as fotos reais do vendedor.

Limites atuais de media por produto:

- até **2 fotos** JPG, PNG ou WebP, 8 MB cada;
- até **1 vídeo** de no máximo 30 segundos, quando adicionado pela página de media.

## Moderação

A moderação combina:

1. regras locais explícitas para conteúdo proibido;
2. denúncias dos utilizadores;
3. revisão humana pela administração.

## Configuração

Copia `.env.example` e define apenas os segredos necessários.

Principais variáveis:

```text
DATABASE_URL=
B2_KEY_ID=
B2_APP_KEY=
B2_BUCKET=pensador-sem-fronteiras-media
B2_REGION=us-east-005
B2_MEDIA_PREFIX=
SESSION_SECRET_KEY=
SESSION_COOKIE_SECURE=false
MAX_POSTS_PER_USER_PER_DAY=10
ADMIN_EMAIL=
```

Nunca publiques senhas ou chaves no repositório.

## Backblaze B2 — configuração e troca de chaves

O Boladas guarda fotos e vídeos no bucket `pensador-sem-fronteiras-media` usando a API S3 compatível do Backblaze B2.

As credenciais usadas pela aplicação são:

- `B2_KEY_ID`: Key ID da Application Key;
- `B2_APP_KEY`: Application Key secreta;
- `B2_BUCKET`: nome exato do bucket;
- `B2_REGION`: região do bucket, atualmente `us-east-005`;
- `B2_MEDIA_PREFIX`: prefixo opcional. Deixa vazio quando a chave tem acesso ao bucket inteiro.

### Permissões necessárias

A Application Key deve permitir ao Boladas, no bucket configurado:

- enviar ficheiros;
- ler ficheiros;
- consultar metadados dos ficheiros;
- eliminar ficheiros quando necessário.

Se a chave estiver limitada por `File name prefix`, esse prefixo deve permitir pelo menos os caminhos usados pela aplicação, incluindo `posts/`, `users/` e `businesses/`. Se não houver necessidade de restringir por pasta, é mais simples deixar o prefixo vazio e limitar a chave apenas ao bucket `pensador-sem-fronteiras-media`.

Um erro `403 Forbidden` em operações `HeadObject`, `GetObject` ou `PutObject` indica normalmente que a chave existe, mas não tem autorização suficiente para o bucket ou prefixo solicitado, ou que a chave está associada a outro bucket.

### Trocar a chave no Render

1. No Backblaze B2, cria uma nova **Application Key** com acesso ao bucket `pensador-sem-fronteiras-media` e com permissões de leitura e escrita necessárias para os ficheiros do Boladas.
2. Guarda o **Key ID** e a **Application Key** no momento da criação. O Backblaze pode não voltar a mostrar a Application Key secreta depois.
3. No Render, abre o serviço `boladas-ponto-com`.
4. Abre **Environment**.
5. Substitui `B2_KEY_ID` pelo novo Key ID.
6. Substitui `B2_APP_KEY` pela nova Application Key.
7. Confirma que `B2_BUCKET=pensador-sem-fronteiras-media`.
8. Confirma que `B2_REGION=us-east-005`.
9. Mantém `B2_MEDIA_PREFIX` vazio, a menos que a Application Key tenha sido criada com uma restrição de prefixo compatível.
10. Guarda as variáveis e deixa o Render reiniciar/reimplantar o serviço.
11. Abre `/estado` e confirma que o diagnóstico do Backblaze aparece como ligado.
12. Publica um anúncio de teste com uma foto real para confirmar leitura e escrita completas.

### Trocar a chave localmente

No ficheiro `.env` local, altera apenas os valores secretos:

```text
B2_KEY_ID=NOVO_KEY_ID
B2_APP_KEY=NOVA_APPLICATION_KEY
B2_BUCKET=pensador-sem-fronteiras-media
B2_REGION=us-east-005
B2_MEDIA_PREFIX=
```

Depois reinicia a aplicação.

### Rotação segura

Quando uma chave for substituída:

1. cria primeiro a nova chave;
2. configura e testa a nova chave no Render;
3. confirma que fotos podem ser enviadas e abertas;
4. só depois revoga a chave antiga no Backblaze.

Nunca coloques `B2_APP_KEY` no README, `.env.example`, código-fonte, commit, issue, Pull Request ou mensagem de log. Apenas os nomes das variáveis devem aparecer no repositório.

## Executar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Sem `DATABASE_URL`, o ambiente local usa `data/posts.db`.

## Testes

```bash
pytest -q
```

## Princípio do produto

O Boladas apresenta apenas informação fornecida pelos utilizadores e dados efetivamente armazenados pelos serviços configurados. Falhas de banco ou armazenamento devem ser mostradas como falhas reais, sem simular sucesso.
