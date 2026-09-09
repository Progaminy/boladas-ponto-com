# Boladas-ponto-com

**Do zero ao infinito.**

Boladas-ponto-com é uma plataforma de anúncios, lojas, comparação de preços e contacto entre compradores e vendedores. O backend é FastAPI + Jinja2, os dados estruturados podem usar PostgreSQL/Supabase em produção e as fotos/ficheiros são armazenados no Backblaze B2.

## Estado atual da publicação

O fluxo de anúncios foi simplificado:

- cada produto deve ter **1 ou 2 fotos reais**;
- a primeira foto é a imagem principal do anúncio/feed;
- o Boladas **não gera imagens por IA** para os anúncios;
- IA pode continuar a ajudar apenas em texto, descrição, legenda, categoria e moderação;
- fotos, manifestos e outros ficheiros continuam no **Backblaze B2**;
- utilizadores, empresas, posts, mensagens e restantes dados estruturados ficam no banco relacional.

## Arquitetura

```text
GitHub Pages
    |
    v
Render / FastAPI
    |------------- Supabase PostgreSQL
    |
    +------------- Backblaze B2
```

- **GitHub Pages**: entrada pública do projeto.
- **Render**: executa o FastAPI/Docker.
- **Supabase PostgreSQL**: banco principal de produção quando `DATABASE_URL` está configurada.
- **SQLite**: fallback para desenvolvimento/testes locais quando `DATABASE_URL` não existe.
- **Backblaze B2**: fotos, ficheiros e proveniência.

## Princípio: Nunca fingir

A aplicação não deve dizer que um ficheiro foi guardado quando o B2 não confirmou o upload. O armazenamento faz verificação após o envio e erros reais devem chegar ao utilizador de forma explícita.

## Instalação local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Depois preenche `.env`.

### Banco de dados

Produção com Supabase/PostgreSQL:

```dotenv
DATABASE_URL=postgresql://UTILIZADOR:SENHA@HOST:5432/postgres
```

Para desenvolvimento/testes locais, deixa `DATABASE_URL` vazia e a aplicação usa `data/posts.db` (SQLite).

## Backblaze B2

As credenciais **nunca devem ser colocadas no README, no código, no `render.yaml`, em commits, issues ou Pull Requests**.

O projeto lê estas variáveis de ambiente:

```dotenv
B2_KEY_ID=
B2_APP_KEY=
B2_BUCKET=pensador-sem-fronteiras-media
B2_REGION=us-east-005
B2_MEDIA_PREFIX=
```

### As duas partes de uma Application Key

Ao criar uma nova chave no Backblaze, guarda as duas partes:

1. **Key ID** → colocar em `B2_KEY_ID`.
2. **Application Key** (segredo) → colocar em `B2_APP_KEY`.

Uma parte sem a outra não é suficiente para o Boladas autenticar no B2.

### Trocar a chave no computador local

1. Cria a nova Application Key no Backblaze.
2. Abre o ficheiro `.env` local.
3. Substitui apenas:

```dotenv
B2_KEY_ID=NOVO_KEY_ID
B2_APP_KEY=NOVA_APPLICATION_KEY
```

4. Mantém `B2_BUCKET` e `B2_REGION` se o bucket continuar o mesmo.
5. Reinicia o FastAPI:

```bash
uvicorn app.main:app --reload
```

6. Abre `/estado` e confirma que o Backblaze B2 está autenticado.
7. Faz um anúncio de teste com 1 ou 2 fotos.

### Trocar a chave no Render

No serviço `boladas-ponto-com`:

1. Abre **Render Dashboard → boladas-ponto-com → Environment**.
2. Atualiza `B2_KEY_ID` com o novo Key ID.
3. Atualiza `B2_APP_KEY` com a nova Application Key.
4. Confirma que continuam corretos:

```text
B2_BUCKET=pensador-sem-fronteiras-media
B2_REGION=us-east-005
```

5. Se a chave estiver limitada a um prefixo, ajusta `B2_MEDIA_PREFIX` conforme a permissão da chave. Se a chave tiver acesso ao bucket inteiro, deixa `B2_MEDIA_PREFIX` vazio.
6. Guarda as alterações.
7. Faz **redeploy/restart** do serviço.
8. Testa `https://boladas-ponto-com.onrender.com/estado`.
9. Publica um anúncio de teste com foto.
10. Só depois de confirmar que a nova chave funciona, revoga a chave antiga no Backblaze.

### Porque é necessário reiniciar após trocar a chave

`app/config.py` lê `B2_KEY_ID`, `B2_APP_KEY` e `B2_BUCKET` quando o processo inicia. Além disso, `app/storage.py` mantém o backend B2 em memória depois da primeira utilização. Portanto, trocar o valor no painel sem reiniciar pode deixar o processo antigo a usar as credenciais anteriores.

**Regra:** mudou `B2_KEY_ID` ou `B2_APP_KEY` → reinicia/redeploy o serviço.

### Como saber se a nova chave foi reconhecida por todo o projeto

Depois do restart:

1. `/estado` deve mostrar B2 configurado e autenticado.
2. Publica um produto com uma foto.
3. Confirma que a foto aparece no anúncio/feed.
4. Publica com duas fotos e confirma a galeria.
5. Testa uma foto de perfil/capa se estiveres a usar essas funções.
6. Se aparecer `not entitled`, a chave existe mas não tem permissão para o caminho usado; revê o escopo/prefixo da Application Key e `B2_MEDIA_PREFIX`.

### Rotação segura de chave

Procedimento recomendado para produção:

```text
Criar nova chave
      ↓
Adicionar nova chave no Render
      ↓
Restart / Redeploy
      ↓
Validar /estado + upload real
      ↓
Revogar chave antiga
```

Nunca revogues a chave antiga antes de confirmar que a nova funciona, a menos que a chave antiga tenha sido comprometida.

## Variáveis de ambiente principais

Exemplo sem credenciais reais:

```dotenv
DATABASE_URL=

B2_KEY_ID=
B2_APP_KEY=
B2_BUCKET=pensador-sem-fronteiras-media
B2_REGION=us-east-005
B2_MEDIA_PREFIX=

AI_PROVIDER=auto
VERTEX_EXPRESS_API_KEY=
GEMINI_CHAT_MODEL=gemini-flash-latest
GMI_API_KEY=
GMI_CHAT_MODEL=deepseek-ai/DeepSeek-V3-0324

SESSION_SECRET_KEY=
SESSION_COOKIE_SECURE=true
MAX_POSTS_PER_USER_PER_DAY=10
ADMIN_EMAIL=
```

## Deploy no Render

O repositório inclui `render.yaml` e `Dockerfile`.

O `render.yaml` já declara como segredos externos (`sync: false`):

- `DATABASE_URL`
- `B2_KEY_ID`
- `B2_APP_KEY`
- `B2_MEDIA_PREFIX`
- chaves de IA

Isto significa que esses valores são configurados no painel do Render e **não ficam no repositório público**.

Fluxo de deploy:

1. Render usa a branch `main`.
2. Constrói o Dockerfile.
3. Lê as variáveis de ambiente do serviço.
4. FastAPI inicia.
5. `app/config.py` carrega as credenciais atuais.
6. O B2 é inicializado quando a aplicação precisa guardar/ler um ficheiro.

Health check:

```text
/health
```

Diagnóstico de serviços externos:

```text
/estado
```

## Fotos de produtos

No formulário `/criar`:

- mínimo: **1 foto**;
- máximo: **2 fotos**;
- formatos aceites: JPG, PNG e WebP;
- até 8 MB por foto;
- a primeira foto é usada como imagem principal.

As fotos próprias do vendedor substituem completamente o antigo processo de geração de imagem por IA.

## Testes

```bash
pytest -q
```

Para um teste real com Backblaze, usa credenciais apenas no `.env` local ou nas Environment Variables do Render. Nunca escrevas a chave dentro de um teste versionado.

## Segurança de credenciais

- `.env` não deve ser commitado.
- Não colocar chaves reais em `README.md`.
- Não colocar chaves reais em `render.yaml`.
- Não colocar segredos em JavaScript/browser.
- Não colocar segredos em screenshots públicos.
- Uma chave temporária de testes deve ser revogada/trocada antes do uso definitivo.

Se uma chave real for publicada acidentalmente num repositório ou log público, considera-a comprometida e cria outra imediatamente.

## Rotas úteis

Sem sessão:

- `/` — apresentação
- `/explorar` — feed
- `/empresas` — lojas/empresas
- `/comparar` — comparação de preços/GPS
- `/estado` — diagnóstico real dos serviços externos
- `/health` — health check

Com sessão:

- `/criar` — publicar produto
- `/empresa` — gerir empresas
- `/perfil/fotos` — fotos do perfil
- `/historico` — histórico de posts
- `/mensagens` — mensagens
- `/transacoes` — transações

## Contacto e pagamentos

O Boladas-ponto-com não processa nem retém dinheiro dos utilizadores. A plataforma atua como marketplace/apoio de contacto e mediação; qualquer mecanismo futuro de custódia de fundos exigiria análise legal e regulatória própria.
