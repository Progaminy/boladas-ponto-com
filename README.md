# Boladas-ponto-com

**Crie posts. Guarde a origem.**

Aplicação de geração de posts para redes sociais criada para o **Backblaze Generative Media Hackathon**. Transforma o briefing de um negócio (tema, produto/serviço, público-alvo, tom, chamada para ação, categoria, preço em Metical, localização e contacto) num post pronto a publicar — imagem 1080×1080, legenda, chamada para ação e hashtags — usando o SDK **[Genblaze](https://github.com/backblaze-labs/genblaze)** com o provedor **GMICloud**, e guarda tudo no **Backblaze B2** com um manifesto de proveniência verificável (SHA-256).

Serve tanto empresas com marca própria (estilizadas por categoria de negócio) como utilizadores simples que querem anunciar sem ter uma marca. Cada utilizador regista-se, pode opcionalmente registar um negócio (ex.: uma confeitaria) com perfil público, publica posts em nome próprio ou do negócio, e qualquer visitante — sem conta — pode navegar/explorar por categoria e localização para comparar preços entre negócios. O número `872599084` é o contacto fixo da plataforma para mediação entre compradores e vendedores.

## Princípio: Nunca fingir

Um post só aparece como `completed` depois de o Genblaze gerar realmente a imagem/legenda e de cada ficheiro ser confirmado no Backblaze B2 (via `head()` pós-upload). Falhas de geração ou de upload aparecem como `failed`, com o erro real — nunca como sucesso simulado.

## Stack

- **Backend + frontend**: FastAPI + Jinja2 (um único serviço Python).
- **Geração**: [`genblaze`](https://pypi.org/project/genblaze-core/) (`genblaze-core` + `genblaze-gmicloud` + `genblaze-s3`) — imagem via GMICloud (`GMICloudImageProvider`, modelo `seedream-5.0-lite` por omissão) e legenda/CTA/hashtags via `chat()` da GMICloud (modelo `deepseek-ai/DeepSeek-V3` por omissão).
- **Armazenamento**: Backblaze B2, bucket `pensador-sem-fronteiras-media`, layout `posts/<post_id>/{image.png,caption.txt,provenance.json,thumbnail.webp}` — este layout não depende do utilizador que criou o post (multiutilizador é só ao nível da base de dados da app, não do B2).
- **Autenticação**: registo/login com password (hash `bcrypt`) e sessão assinada por cookie (`itsdangerous`/`SessionMiddleware`).
- **Base de dados local**: SQLite (`data/posts.db`) — utilizadores, negócios e posts (histórico privado por utilizador).

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copia `.env.example` para `.env` e preenche as credenciais reais (nunca commitadas):

```bash
cp .env.example .env
```

```dotenv
B2_KEY_ID=...          # https://secure.backblaze.com/app_keys.htm
B2_APP_KEY=...
B2_BUCKET=pensador-sem-fronteiras-media
GMI_API_KEY=...        # https://console.gmicloud.ai/
SESSION_SECRET_KEY=... # python3 -c "import os; print(os.urandom(32).hex())"
```

Sem estas variáveis, a aplicação continua a arrancar e a servir as páginas, mas qualquer tentativa de gerar um post falha de forma explícita (respeitando "Nunca fingir") em vez de simular um resultado.

## Correr localmente

```bash
vicorn aupp.main:app --reload
```
http://127.0.0.1:8000


Público (sem sessão):
- `http://localhost:8000/explorar` — página inicial: galeria pública de negócios, filtrável por categoria e localização
- `http://localhost:8000/registar`, `http://localhost:8000/entrar` — criar conta / iniciar sessão
- `http://localhost:8000/negocio/<business_id>` — perfil público de um negócio
- `http://localhost:8000/posts/<post_id>` — resultado de um post (partilhável)
- `http://localhost:8000/posts/<post_id>/provenance` — proveniência (lida em tempo real do B2)
- `http://localhost:8000/health` — estado da configuração (B2/GMICloud ligados ou não)

Requer sessão (redireciona para `/entrar` se não autenticado):
- `http://localhost:8000/criar` — formulário de criação de post
- `http://localhost:8000/empresa` — registar/editar o negócio próprio
- `http://localhost:8000/historico` — histórico privado dos meus posts (inclui `pending`/`failed`)

## Testes

```bash
pytest -q
```

Os testes cobrem a formatação das chaves e verificação de upload no B2 (com um backend simulado), o schema do `provenance.json`, as funções puras do pipeline (construção de prompts, parsing de JSON, redimensionamento de imagem para 1080×1080), e o fluxo de autenticação/sessão (registo, login, proteção de rotas) com uma base de dados SQLite isolada por teste. Não exercitam chamadas reais ao GMICloud/B2 — para isso é necessário `.env` com credenciais reais e correr a aplicação manualmente.

## Estrutura

```
app/
├── main.py            # app FastAPI, SessionMiddleware, monta routers, health-check
├── config.py           # variáveis de ambiente, contacto da plataforma
├── models.py            # Pydantic: PostInput, UserCreate, BusinessInput, PostStatus...
├── categories.py         # categorias de negócio → cor/estilo de imagem
├── auth.py                # hash de password (bcrypt), sessão, get_current_user
├── db.py                   # SQLite: users, businesses, posts
├── pipeline.py              # geração real via Genblaze + GMICloud
├── storage.py                # upload/verificação no B2, SHA-256
├── provenance.py               # montagem do provenance.json
├── routers/                     # auth, business, explore, posts, history, provenance
├── templates/                    # registar, entrar, empresa, explorar, criar,
│                                   resultado, histórico, proveniência
└── static/                        # css/js
tests/                              # pytest
```

## Conta de teste para os jurados

A aplicação exige sessão para criar posts/negócio, mas a navegação pública (`/explorar`,
perfis de negócio, resultado de posts) não precisa de conta. Para os jurados testarem o
fluxo autenticado, cria-se uma conta de demonstração após o deploy:

```bash
curl -X POST https://<url-pública>/registar \
  -d "email=jurado@boladas.test&password=<password-forte>&display_name=Jurado"
```

(ou simplesmente usar o formulário em `/registar`). As credenciais finais de demonstração
serão indicadas na submissão do Devpost, conforme exigido pelas regras oficiais do hackathon
para aplicações com login.

## Estado atual

MVP funcional: registo/login, perfil de negócio opcional, criação de post que recebe o
briefing, valida, gera imagem + legenda + hashtags via Genblaze/GMICloud, calcula SHA-256,
envia para o B2 com verificação, monta o manifesto de proveniência, histórico privado por
utilizador, e galeria pública para explorar/comparar negócios por categoria e localização.
Por fazer: deploy para URL pública, conta de demonstração para os jurados, vídeo de
demonstração.
