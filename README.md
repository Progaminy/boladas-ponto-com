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
