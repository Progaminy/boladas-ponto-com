# Boladas-ponto-com

**Crie posts. Guarde a origem.**

Aplicação de geração de posts para redes sociais criada para o **Backblaze Generative Media Hackathon**. Transforma o briefing de um negócio (tema, produto/serviço, público-alvo, tom, chamada para ação, categoria, preço em Metical, localização e contacto) num post pronto a publicar — imagem 1080×1080, legenda, chamada para ação e hashtags — usando o SDK **[Genblaze](https://github.com/backblaze-labs/genblaze)** com o provedor **GMICloud**, e guarda tudo no **Backblaze B2** com um manifesto de proveniência verificável (SHA-256).

Serve tanto empresas com marca própria (estilizadas por categoria de negócio, entre ~29 categorias, ou uma categoria personalizada escrita à mão) como utilizadores simples que querem anunciar sem ter uma marca. Cada utilizador regista-se, pode registar quantas empresas quiser (cada uma com o seu próprio perfil, categoria e fotos), publica posts em nome próprio ou de qualquer uma delas — o formulário fica simples por omissão para uma venda pessoal/eventual, e só pede os detalhes de marketing quando publicas como empresa — e explora os posts de outros negócios por categoria e localização para comparar preços — isto exige conta, como no Facebook. Já cada post individual e a sua proveniência têm uma página pública e partilhável (sem conta), para poderem ser divulgados e verificados por qualquer pessoa — a menos que tenha sido reportado e esteja pendente de revisão (ver moderação abaixo). O número `872599084` é o contacto fixo da plataforma para mediação entre compradores e vendedores.

## Princípio: Nunca fingir

Um post só aparece como `completed` depois de o Genblaze gerar realmente a imagem e a legenda, e de cada ficheiro ser confirmado no Backblaze B2 — não por um simples `head()`, mas descarregando os bytes de volta e comparando o SHA-256 com o que foi enviado. Falhas de geração ou de upload aparecem como `failed`, com o erro real — nunca como sucesso simulado.

Isto vale para o resto da aplicação:

- **A proveniência é auditável, não decorativa.** Qualquer pessoa (sem conta) pode carregar em *Verificar contra o Backblaze B2 agora* na página de proveniência: a aplicação vai buscar os ficheiros ao bucket naquele momento, recalcula o hash e mostra o resultado por ficheiro. Se alguém substituir um objeto no bucket mantendo a chave, aparece como não conferindo — há um teste que faz exatamente isso.
- **O diagnóstico testa mesmo as ligações.** `/estado` autentica-se contra o B2 e consulta o catálogo do GMICloud, em vez de se limitar a confirmar que existem variáveis de ambiente. Uma chave válida é reportada como válida — e com a ressalva explícita de que isso não implica saldo disponível.
- **Capacidades que não existem não são simuladas.** Não há moderação visual automática de fotos/vídeo porque não há uma API de visão verificada disponível; em vez de fingir que há, essa lacuna é coberta por reporte com revisão humana e está documentada como tal.

## Stack

- **Backend + frontend**: FastAPI + Jinja2 (um único serviço Python).
- **Geração**: [`genblaze`](https://pypi.org/project/genblaze-core/) (`genblaze-core` + `genblaze-gmicloud` + `genblaze-s3`) — imagem via GMICloud (`GMICloudImageProvider`, modelo `seedream-5.0-lite` por omissão) e legenda/CTA/hashtags via `chat()` da GMICloud (modelo `deepseek-ai/DeepSeek-V3-0324` por omissão — lista completa de modelos disponíveis em `GET https://api.gmi-serving.com/v1/models` com a tua `GMI_API_KEY`).
- **Armazenamento**: Backblaze B2, bucket `pensador-sem-fronteiras-media`, layout `posts/<post_id>/{image.png,caption.txt,provenance.json,thumbnail.webp}` — este layout não depende do utilizador que criou o post (multiutilizador é só ao nível da base de dados da app, não do B2).
- **Autenticação**: registo/login com password (hash `bcrypt`) e sessão assinada por cookie (`itsdangerous`/`SessionMiddleware`).
- **Base de dados local**: SQLite (`data/posts.db`) — utilizadores, negócios e posts (histórico privado por utilizador).
- **Composição da imagem**: a IA gera a imagem sem texto embutido (texto gerado por modelos de imagem costuma sair deformado); nome do negócio, preço em MT e chamada para ação são depois desenhados de forma determinística com Pillow (fonte DejaVu incluída no repositório), na cor da categoria — o `image.png` final já sai pronto a publicar.
- **Limite de geração**: no máximo `MAX_POSTS_PER_USER_PER_DAY` (10 por omissão) posts por utilizador a cada 24h, para proteger os créditos do GMICloud.
- **Média do produto**: até 4 fotos e 1 vídeo de 30s reais por post (para além da imagem gerada por IA), com validação real (Pillow reabre a imagem; `ffmpeg`/`ffprobe` mede a duração do vídeo — nunca confia só na extensão/`content_type` declarado pelo browser).
- **Mensagens ("Boladas Message")**: contacto interno entre utilizadores sempre associado ao post/produto em causa, mais um canal separado para contactar a equipa da plataforma para ajuda/mediação.
- **Termos de Uso**: aceitação obrigatória no registo (`/termos`), deixando explícito que a plataforma não processa nem retém pagamentos.
- **Transações**: checklist de confiança entre comprador e vendedor (`pendente → vendido → recebido`, com opção de mediação da equipa) — sem custódia de dinheiro (ver nota em "Estado atual").
- **Moderação**: lista de bloqueio de texto (sem custo, aplicada antes de gastar créditos GMICloud a gerar o post) + classificação por IA via `chat()` quando há saldo GMICloud; qualquer utilizador pode reportar um post (incluindo fotos/vídeo, que não têm verificação visual automática — não existe API de visão verificada disponível), ocultando-o até um admin decidir em `/admin/moderacao`.
- **Categorias e cor da plataforma**: cor oficial roxo escuro na interface; ~29 categorias com cores coerentes por omissão (ex.: farmácia branco, eletricidade laranja, mecânica azul-escuro); qualquer categoria fora da lista é aceite tal como escrita (nunca bloqueada), e há um botão para sugerir a categoria automaticamente a partir da descrição via IA (também depende de saldo GMICloud).
- **Fotos de perfil/capa**: uma foto de perfil e uma de capa para a conta pessoal, e o mesmo por cada empresa registada — com perfil público em `/utilizador/<id>` e `/negocio/<id>`.
- **Verificação de proveniência ao vivo**: `POST /posts/<id>/verificar` (público) volta a descarregar do B2 cada ficheiro declarado no manifesto e recalcula o SHA-256, com resultado por ficheiro.
- **Diagnóstico do sistema**: `/estado` exercita mesmo as ligações ao B2 e ao GMICloud e mostra o erro real do serviço quando algo falha.
- **Interface móvel**: a maioria dos acessos em Moçambique é por telemóvel, por isso o layout é responsivo (campos empilham, navegação quebra em linhas, filtros ficam a largura total).

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
B2_REGION=us-east-005
GMI_API_KEY=...        # https://console.gmicloud.ai/
SESSION_SECRET_KEY=... # python3 -c "import os; print(os.urandom(32).hex())"
MAX_POSTS_PER_USER_PER_DAY=10
ADMIN_EMAIL=teu-email@exemplo.co.mz  # quem se registar com este email fica admin
```

Sem estas variáveis, a aplicação continua a arrancar e a servir as páginas, mas qualquer tentativa de gerar um post falha de forma explícita (respeitando "Nunca fingir") em vez de simular um resultado.

## Correr localmente

```bash
uvicorn app.main:app --reload
```
http://127.0.0.1:8000


Sem sessão:
- `/` — página de apresentação (quem já tem sessão vai direto para `/explorar`)
- `/registar`, `/entrar` — criar conta / iniciar sessão
- `/termos` — Termos de Uso
- `/estado` — diagnóstico real das ligações ao B2 e ao GMICloud
- `/health` — health-check leve para o Render (não contacta serviços externos)
- `/posts/<post_id>` e `/posts/<post_id>/provenance` — resultado e proveniência de um post, partilháveis (ex.: WhatsApp) e verificáveis por qualquer pessoa, incluindo os jurados, sem precisar de conta
- `POST /posts/<post_id>/verificar` — verificação ao vivo do SHA-256 contra o B2

Requer sessão (redireciona para `/entrar` se não autenticado):
- `/explorar` — galeria de negócios, filtrável por categoria e localização
- `/criar` — formulário de criação de post
- `/empresa` — lista das minhas empresas; `/empresa/nova` — registar outra; `/negocio/<business_id>` — perfil público
- `/perfil/fotos` e `/empresa/<id>/fotos` — fotos de perfil e capa
- `/historico` — histórico privado dos meus posts (inclui `pending`/`failed`)
- `/mensagens`, `/transacoes` — conversas e estado das compras/vendas
- `/admin/moderacao` — fila de revisão (apenas admins)

## Testes

```bash
pytest -q
```

83 testes, todos sem custo e sem tocar em serviços externos (backend B2 simulado e base de dados SQLite isolada por teste). Cobrem, entre outros:

- upload no B2 verificado por tamanho **e** SHA-256 remoto, incluindo um cenário de corrupção silenciosa (mesmo tamanho, conteúdo diferente);
- verificação de proveniência ao vivo, incluindo deteção de um objeto adulterado no bucket e relato honesto de um ficheiro em falta;
- schema do `provenance.json` e ausência de credenciais no manifesto;
- funções puras do pipeline (prompts, parsing de JSON, redimensionamento para 1080×1080) e a sobreposição de texto na imagem;
- validação real de média (Pillow para imagens; um vídeo de 35s gerado com `ffmpeg` é rejeitado por exceder os 30s);
- autenticação, proteção de rotas, limite diário de geração, máquina de estados das transações e moderação;
- diagnóstico, incluindo a garantia de que `/health` não contacta serviços externos.

Há ainda um teste de integração **real** (`tests/test_integration_live.py`), desativado por omissão para nunca gastar créditos sem intenção:

```bash
set -a && source .env && set +a
RUN_LIVE_INTEGRATION_TESTS=1 pytest -q tests/test_integration_live.py -v -s
```

Gera um post verdadeiro via GMICloud, envia-o para o bucket real, confirma os hashes e remove o post de teste no fim.

## Estrutura

```
app/
├── main.py            # app FastAPI, SessionMiddleware, routers, /health e /estado
├── config.py           # variáveis de ambiente, contacto da plataforma
├── models.py            # Pydantic: PostInput, UserCreate, BusinessInput, PostStatus...
├── categories.py         # ~29 categorias de negócio → cor/estilo de imagem
├── category_classify.py   # sugestão de categoria via IA (opcional, GMICloud)
├── auth.py                 # hash de password (bcrypt), sessão, get_current_user
├── db.py                    # SQLite: users, businesses (várias por user), posts,
│                             # messages, product_media, transactions, reports
├── pipeline.py                # geração real via Genblaze + GMICloud
├── image_compose.py            # sobrepõe nome/preço/CTA na imagem com Pillow
├── media_validate.py            # valida fotos/vídeo (Pillow + ffprobe), limites reais
├── moderation.py                 # lista de bloqueio de texto + classificação IA opcional
├── storage.py                     # upload/verificação (SHA-256 remoto) no B2
├── provenance.py                   # montagem do provenance.json
├── verify.py                        # verificação ao vivo do manifesto contra o B2
├── diagnostics.py                    # testa mesmo as ligações externas (/estado)
├── routers/                           # auth, business, explore, messages, media,
│                                        transactions, moderation, profile, posts,
│                                        history, provenance
├── templates/                          # landing, registar, entrar, termos, estado,
│                                         empresa (lista/criar/editar), explorar, criar,
│                                         resultado, histórico, proveniência, inbox,
│                                         thread, media_form, transactions,
│                                         admin_moderation, photos_form, user_profile
└── static/                            # css/js/fonts (DejaVu, para o overlay)
tests/                                  # pytest
```

Dockerfile na raiz (usado pelo deploy no Render) instala `ffmpeg` para a validação real de vídeo.

## Conta de teste para os jurados

Registo/login, explorar, criar posts, histórico e perfil de negócio exigem sessão. A página
de resultado de um post e a sua proveniência (`/posts/<id>` e `/posts/<id>/provenance`) são
públicas e partilháveis, para poderem ser verificadas sem conta. Para os jurados testarem o
fluxo completo (criar posts, ver histórico, negócio), cria-se uma conta de demonstração após
o deploy:

```bash
curl -X POST https://<url-pública>/registar \
  -d "email=jurado@boladas.test&password=<password-forte>&display_name=Jurado"
```

(ou simplesmente usar o formulário em `/registar`). As credenciais finais de demonstração
serão indicadas na submissão do Devpost, conforme exigido pelas regras oficiais do hackathon
para aplicações com login.

## Deploy (Render)

O repositório inclui um `render.yaml` (Blueprint) pronto:

1. No [dashboard do Render](https://dashboard.render.com/), **New → Blueprint**, aponta para
   este repositório GitHub.
2. O Render lê o `render.yaml` e o `Dockerfile` e cria um Web Service Docker (não o runtime
   Python nativo do Render) — é preciso Docker especificamente para instalar `ffmpeg`, usado
   para validar a duração real dos vídeos de produto (ver `app/media_validate.py`); o runtime
   Python nativo não permite instalar binários do sistema.
3. Preenche os valores marcados `sync: false` no dashboard (nunca vão no `render.yaml`,
   que é público no repositório): `B2_KEY_ID`, `B2_APP_KEY`, `GMI_API_KEY`.
   `SESSION_SECRET_KEY` é gerada automaticamente pelo Render (`generateValue: true`).
4. Deploy. A URL pública fica em `https://boladas-ponto-com.onrender.com` (ou o nome que o
   Render atribuir).

**Limitação conhecida:** `data/posts.db` (SQLite) vive no disco do serviço. No plano free do
Render o disco não é persistente entre deploys/reinícios — os utilizadores/negócios/histórico
locais perdem-se nesses momentos (os ficheiros já gerados no Backblaze B2 não são afetados,
só o índice local). Para persistência real seria preciso um disco pago do Render ou migrar
para uma base de dados gerida (ex. PostgreSQL do Render). Para a demonstração do hackathon
isto é aceitável, mas é uma limitação a resolver antes de um uso real em produção.

## Estado atual

**Verificado a funcionar contra os serviços reais:** a ligação ao Backblaze B2 está
operacional (upload, verificação por SHA-256 e remoção testados com as credenciais reais), e
a chave do GMICloud é válida — o catálogo devolve 78 modelos, incluindo os que a aplicação
usa por omissão.

**Implementado:** registo/login com Termos de Uso, várias empresas por utilizador com perfis
e fotos, formulário de criação que fica simples para uma venda pessoal e completo para uma
empresa, geração via Genblaze/GMICloud com sobreposição determinística de nome/preço/CTA,
armazenamento no B2 com verificação por hash, manifesto de proveniência (com o manifesto
nativo do Genblaze embutido) e verificação ao vivo desse manifesto, histórico privado,
galeria com filtros, mensagens ligadas ao produto, média real do produto (4 fotos + vídeo de
30s validados), rastreio de transações, moderação com revisão humana, diagnóstico do sistema
e interface responsiva.

**Bloqueado por saldo, não por código:** a conta GMICloud está sem créditos, o que devolve
`402 Insufficient credits` tanto na geração de imagem como no `chat()`. Está confirmado que
a aplicação lida com isso corretamente — o post fica `failed` com a mensagem real do
serviço, sem estados presos nem sucessos simulados. Assim que houver saldo, a geração real
ponta a ponta pode ser confirmada com o teste de integração acima, sem alterar código.

**Por fazer:** gerar os posts reais de demonstração (depende do saldo), deploy para a URL
pública, conta de demonstração para os jurados e o vídeo de apresentação.

**Nota sobre pagamentos:** o Boladas-ponto-com não processa nem retém dinheiro de
utilizadores. Um mecanismo desse tipo (custódia/escrow) exigiria licenciamento como
instituição de pagamento, o que está fora do âmbito deste MVP.

**Nota sobre moderação visual:** não existe verificação automática de conteúdo em
fotos/vídeo — não há uma API de visão verificada disponível para isto. Fotos/vídeo (e texto
que passe as duas camadas automáticas) ficam cobertos pelo mecanismo de reportar + revisão
humana, não por deteção automática.
