# Boladas-ponto-com

**Crie posts. Guarde a origem.**

Aplicação de geração de posts para redes sociais criada para o **Backblaze Generative Media Hackathon**. Transforma o briefing de um negócio (tema, produto/serviço, público-alvo, tom, chamada para ação, categoria, preço em Metical, localização e contacto) num post pronto a publicar — imagem 1080×1080, legenda, chamada para ação e hashtags — usando o SDK **[Genblaze](https://github.com/backblaze-labs/genblaze)** com **Gemini (Vertex AI Express)** como provedor principal e **GMICloud** como alternativa, e guarda tudo no **Backblaze B2** com um manifesto de proveniência verificável (SHA-256).

Serve tanto empresas com marca própria (estilizadas por categoria de negócio, entre ~29 categorias, ou uma categoria personalizada escrita à mão) como utilizadores simples que querem anunciar sem ter uma marca. Cada utilizador regista-se, pode registar quantas empresas quiser (cada uma com o seu próprio perfil, categoria e fotos), publica posts em nome próprio ou de qualquer uma delas — o formulário fica simples por omissão para uma venda pessoal/eventual, e só pede os detalhes de marketing quando publicas como empresa — e explora os posts de outros negócios por categoria e localização para comparar preços — isto exige conta, como no Facebook. Já cada post individual e a sua proveniência têm uma página pública e partilhável (sem conta), para poderem ser divulgados e verificados por qualquer pessoa — a menos que tenha sido reportado e esteja pendente de revisão (ver moderação abaixo). O número `872599084` é o contacto fixo da plataforma para mediação entre compradores e vendedores.

## Princípio: Nunca fingir

Um post só aparece como `completed` depois de o Genblaze gerar realmente a imagem e a legenda, e de cada ficheiro ser confirmado no Backblaze B2 — não por um simples `head()`, mas descarregando os bytes de volta e comparando o SHA-256 com o que foi enviado. Falhas de geração ou de upload aparecem como `failed`, com o erro real — nunca como sucesso simulado.

Isto vale para o resto da aplicação:

- **A proveniência é auditável, não decorativa.** Qualquer pessoa (sem conta) pode carregar em *Verificar contra o Backblaze B2 agora* na página de proveniência: a aplicação vai buscar os ficheiros ao bucket naquele momento, recalcula o hash e mostra o resultado por ficheiro. Se alguém substituir um objeto no bucket mantendo a chave, aparece como não conferindo — há um teste que faz exatamente isso.
- **O diagnóstico testa mesmo as ligações.** `/estado` autentica-se contra o B2, consulta os modelos do Vertex e o catálogo do GMICloud, em vez de se limitar a confirmar que existem variáveis de ambiente. Uma chave válida é reportada como válida — e com a ressalva explícita de que isso não implica saldo disponível.
- **"Não verificado" nunca é apresentado como "limpo".** A moderação por IA devolve explicitamente "não verificado" quando a chamada falha, em vez de deixar passar como aprovado; o reporte com revisão humana continua a ser a rede de segurança por baixo.
- **Falhar diz porquê.** Quando todos os provedores de IA falham, o erro apresentado inclui a razão real de cada um — não uma mensagem genérica que esconde a causa.

## Regras do Projeto & Funcionalidades Principais

Qualquer visitante ou utilizador registado pode consultar as seguintes regras e funcionalidades da plataforma:

1. **Diretório Público de Lojas & Empresas (`/empresas`)**:
   - Qualquer utilizador pode visualizar e navegar nas páginas completas de empresas e lojas físicas reais criadas no sistema:
     - **Farmácia Moçambique Vida** (Medicamentos, vitaminas, saúde e bem-estar).
     - **Ferragem Lendária Maputo** (Cimento, tubos PVC, pregos e materiais de construção).
     - **Moda & Estilo Boutique** (Capulanas de luxo, vestidos de gala e vestuário).
     - **Mercado Popular de Xipamanine** (Arroz por grosso, óleo alimentar, feijão e mercearia).
     - **Transporte & Carga Expresso** (Mudanças residenciais e fretes de material).
   - Cada empresa possui uma página personalizada estilo montra profissional com capa, logótipo, NUIT, localização, catálogo de produtos, lista de sócios/gestores e botões de contacto direto (`WhatsApp`, `Ligar`, `Messenger Boladas`).

2. **Comparador de Preços & Detetador de Proximidade GPS (`/comparar`)**:
   - Permite aos utilizadores pesquisar por produto (ex.: *Cimento, Paracetamol, Capulana, Arroz, Mudança*) e comparar instantaneamente os preços em Meticais (`MT`) praticados por diferentes lojas e vendedores.
   - Integração com a API de Geolocalização GPS do navegador (`navigator.geolocation`) para calcular a distância exata em quilómetros (`km`) até à loja física mais próxima (`🚗 1.2 km de distância - Av. 24 de Julho`), facilitando compras presenciais imediatas.

3. **Feed Social Estilo Facebook / TikTok (`/explorar` e `/`)**:
   - Ao aceder à plataforma, o utilizador entra diretamente no Feed Social de Negócios para navegar em fotos de produtos.
   - Cada cartão exibe a foto/avatar do perfil do vendedor ou insígnia SVG dinâmica em gradiente, ID do produto (`#...`), preço em MT, contacto de mediação da plataforma (`872599084`), botões de reações (👍 Like / 👎 Dislike com justificativa auditável) e caixa pública de comentários.

4. **Autonomia Total de Perfil, Edição & Temas Festivos (`/perfil/fotos` e `/empresa/{id}`)**:
   - O utilizador tem controlo total para retificar, editar ou apagar anúncios, atualizar fotos de perfil/capa e ativar temas sazonais/festivos (Natal, Festas de Empresa, etc.) na sua página ou loja a qualquer momento.

5. **Canal e Botão de Assistência Humana (`872599084`)**:
   - A qualquer momento, o utilizador pode carregar no botão `🆘 Pedir Assistência Humana` nas mensagens ou anúncios para abrir uma linha direta de apoio e mediação com a equipa da plataforma Boladas-ponto-com.

6. **Resiliência contra Exaustão de Quota de IA**:
   - Se as APIs de IA (Vertex Gemini / GMICloud) atingirem o limite de requisições (`429 RESOURCE_EXHAUSTED`), o post é concluído como `completed` com a imagem/descrição fornecida pelo utilizador, preservando o upload e proveniência B2 sem nunca bloquear a publicação.

## Stack

- **Backend + frontend**: FastAPI + Jinja2 (um único serviço Python).
- **Geração**: [`genblaze`](https://pypi.org/project/genblaze-core/) (`genblaze-core` + `genblaze-gmicloud` + `genblaze-s3`) com **dois provedores**, definidos por `AI_PROVIDER` (`auto` por omissão: tenta o Vertex primeiro e recorre ao GMICloud):
  - **Gemini via Vertex AI Express** (principal) — `gemini-2.5-flash-image` para imagem e `gemini-2.5-flash` para texto e visão. A imagem é gerada dentro de um `SyncProvider` do Genblaze (`app/gemini_provider.py`), pelo que o `Pipeline`, o manifesto e a cadeia de proveniência se mantêm intactos.
  - **GMICloud** (fallback) — `seedream-5.0-lite` para imagem e `deepseek-ai/DeepSeek-V3-0324` para texto.

  Se todos os provedores configurados falharem, o erro devolvido contém a razão real de cada um.
- **Armazenamento**: Backblaze B2, bucket `pensador-sem-fronteiras-media`, layout `posts/<post_id>/{image.png,caption.txt,provenance.json,thumbnail.webp}` — este layout não depende do utilizador que criou o post (multiutilizador é só ao nível da base de dados da app, não do B2).
- **Autenticação**: registo/login com password (hash `bcrypt`) e sessão assinada por cookie (`itsdangerous`/`SessionMiddleware`).
- **Base de dados local**: SQLite (`data/posts.db`) — utilizadores, negócios e posts (histórico privado por utilizador).
- **Composição da imagem**: a IA gera a imagem sem texto embutido (texto gerado por modelos de imagem costuma sair deformado); nome do negócio, preço em MT e chamada para ação são depois desenhados de forma determinística com Pillow (fonte DejaVu incluída no repositório), na cor da categoria — o `image.png` final já sai pronto a publicar.
- **Limite de geração**: no máximo `MAX_POSTS_PER_USER_PER_DAY` (10 por omissão) posts por utilizador a cada 24h, para proteger os créditos do provedor de IA.
- **Média do produto**: até 4 fotos e 1 vídeo de 30s reais por post (para além da imagem gerada por IA), com validação real (Pillow reabre a imagem; `ffmpeg`/`ffprobe` mede a duração do vídeo — nunca confia só na extensão/`content_type` declarado pelo browser).
- **Mensagens ("Boladas Message")**: contacto interno entre utilizadores sempre associado ao post/produto em causa, mais um canal separado para contactar a equipa da plataforma para ajuda/mediação.
- **Termos de Uso**: aceitação obrigatória no registo (`/termos`), deixando explícito que a plataforma não processa nem retém pagamentos.
- **Transações**: checklist de confiança entre comprador e vendedor (`pendente → vendido → recebido`, com opção de mediação da equipa) — sem custódia de dinheiro (ver nota em "Estado atual").
- **Moderação em três camadas**: (1) lista de bloqueio de texto local, sem custo, aplicada antes de gastar qualquer crédito de geração; (2) classificação textual por IA (Vertex, com GMICloud como fallback); (3) verificação visual real de fotos e vídeo com o Gemini. Qualquer camada de IA devolve "não verificado" — nunca "limpo" — se a chamada falhar. Por baixo de tudo, qualquer utilizador pode reportar um post, ocultando-o até um admin decidir em `/admin/moderacao`.
- **Categorias e cor da plataforma**: cor oficial roxo escuro na interface; ~29 categorias com cores coerentes por omissão (ex.: farmácia branco, eletricidade laranja, mecânica azul-escuro); qualquer categoria fora da lista é aceite tal como escrita (nunca bloqueada), e há um botão para sugerir a categoria automaticamente a partir da descrição via IA (depende de um provedor de IA disponível).
- **Fotos de perfil/capa**: uma foto de perfil e uma de capa para a conta pessoal, e o mesmo por cada empresa registada — com perfil público em `/utilizador/<id>` e `/negocio/<id>`.
- **Empresas com sócios**: uma empresa pode ter vários gestores, cada um com o seu próprio acesso. Todos publicam e editam; só o proprietário acrescenta ou remove gestores, e o proprietário nunca pode ser removido (uma empresa sem dono ficaria inacessível).
- **Cadastro direto de empresa**: `/registar/empresa` cria a conta de acesso e o negócio num só passo, para quem só quer registar a loja e não uma conta pessoal.
- **Verificação de proveniência ao vivo**: `POST /posts/<id>/verificar` (público) volta a descarregar do B2 cada ficheiro declarado no manifesto e recalcula o SHA-256, com resultado por ficheiro.
- **Diagnóstico do sistema**: `/estado` exercita mesmo as ligações ao B2, ao Vertex e ao GMICloud e mostra o erro real do serviço quando algo falha.
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

AI_PROVIDER=auto                 # auto | vertex | gmicloud
VERTEX_EXPRESS_API_KEY=...       # Gemini via Vertex AI Express (principal)
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
GEMINI_CHAT_MODEL=gemini-2.5-flash
GMI_API_KEY=...                  # https://console.gmicloud.ai/ (fallback)

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
- `/estado` — diagnóstico real das ligações ao B2, Vertex e GMICloud
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

Gera um post verdadeiro via o provedor configurado, envia-o para o bucket real, confirma os hashes e remove o post de teste no fim.

## Estrutura

```
app/
├── main.py            # app FastAPI, SessionMiddleware, routers, /health e /estado
├── config.py           # variáveis de ambiente, contacto da plataforma
├── models.py            # Pydantic: PostInput, UserCreate, BusinessInput, PostStatus...
├── categories.py         # ~29 categorias de negócio → cor/estilo de imagem
├── category_classify.py   # sugestão de categoria via IA (Vertex ou GMICloud)
├── auth.py                 # hash de password (bcrypt), sessão, get_current_user
├── db.py                    # SQLite: users, businesses (várias por user), posts,
│                             # messages, product_media, transactions, reports
├── gemini_provider.py          # SyncProvider Genblaze p/ Gemini (Vertex Express)
├── pipeline.py                  # geração real via Genblaze (Vertex/GMICloud)
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

## Contas de exemplo

Registo/login, explorar, criar posts, histórico e perfil de negócio exigem sessão. A página
de resultado de um post e a sua proveniência (`/posts/<id>` e `/posts/<id>/provenance`) são
públicas e partilháveis, para poderem ser verificadas sem conta.

Para explorar a aplicação com dados realistas:

```bash
python3 scripts/seed_exemplos.py
```

Cria cinco contas (password `boladas2026`, todas com email `@exemplo.boladas.mz`), cobrindo
os casos de uso reais:

| Conta | Situação |
|---|---|
| `carlota@` | vende roupa em segunda mão, **sem empresa** |
| `jaime@` | mercado informal — empresa com **categoria escrita à mão** ("Mercado Informal") |
| `ana@` | proprietária da Farmácia Vida Nova |
| `rui@` | **sócio** da mesma farmácia, com acesso próprio |
| `salomao@` | gere **duas empresas** (ferragens e padaria) |

Com `--posts`, cria também anúncios **reais**: a legenda, a chamada para ação e as hashtags
são geradas pela IA de verdade e enviadas para o Backblaze B2, com manifesto de proveniência.

```bash
python3 scripts/seed_exemplos.py --posts
```

Como o plano gratuito só permite 20 gerações por dia (ver abaixo), o script pode não conseguir
criar todos os anúncios de uma vez — nesse caso diz-o claramente e pára, e correr outra vez no
dia seguinte cria os que faltam sem duplicar os que já existem. Os anúncios ficam sem imagem
gerada, e a página do post mostra-o explicitamente com o motivo real: mostrar uma imagem de
substituição contradiria o princípio "Nunca fingir".

O script é idempotente e `--limpar` remove os exemplos sem tocar em contas reais.

As credenciais de demonstração para os jurados serão indicadas na submissão do Devpost,
conforme exigido pelas regras oficiais do hackathon para aplicações com login.

## Deploy (Render)

O repositório inclui um `render.yaml` (Blueprint) pronto:

1. No [dashboard do Render](https://dashboard.render.com/), **New → Blueprint**, aponta para
   este repositório GitHub.
2. O Render lê o `render.yaml` e o `Dockerfile` e cria um Web Service Docker (não o runtime
   Python nativo do Render) — é preciso Docker especificamente para instalar `ffmpeg`, usado
   para validar a duração real dos vídeos de produto (ver `app/media_validate.py`); o runtime
   Python nativo não permite instalar binários do sistema.
3. Preenche os valores marcados `sync: false` no dashboard (nunca vão no `render.yaml`,
   que é público no repositório): `B2_KEY_ID`, `B2_APP_KEY`, `VERTEX_EXPRESS_API_KEY` e/ou `GMI_API_KEY`.
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

**Verificado a funcionar contra os serviços reais**, com credenciais verdadeiras:

| Capacidade | Estado | Verificação |
|---|---|---|
| Armazenamento no Backblaze B2 | ✅ | Upload, verificação por SHA-256 e remoção testados no bucket real |
| Post completo de ponta a ponta | ✅ | `completed`, com `caption.txt` e `provenance.json` confirmados no bucket |
| Legenda + CTA + hashtags | ✅ | Gerados pelo Gemini em português, com preço e bairro integrados |
| Descrição a partir de uma foto | ✅ | Descreveu uma camisa real (cor, botões, colarinho) sem inventar marca nem tamanho |
| Descrição a partir de explicação | ✅ | Transformou "usei duas vezes, está como nova" numa descrição comercial |
| Sugestão automática de categoria | ✅ | Classificou corretamente farmácia e oficina mecânica |
| Moderação de texto por IA | ✅ | Aprovou anúncio legítimo, sinalizou documentos falsificados |
| Moderação visual (fotos/vídeo) | ✅ | Devolveu veredicto real sobre uma imagem real |
| **Geração de imagem** | ❌ | Bloqueada por quota — ver abaixo |

**Implementado:** registo/login com Termos de Uso, várias empresas por utilizador com perfis
e fotos, formulário de criação que fica simples para uma venda pessoal e completo para uma
empresa, geração via Genblaze (Gemini/Vertex como principal, GMICloud como fallback) com
sobreposição determinística de nome/preço/CTA, armazenamento no B2 com verificação por hash,
manifesto de proveniência (com o manifesto nativo do Genblaze embutido) e verificação ao vivo
desse manifesto, histórico privado, galeria com filtros, mensagens ligadas ao produto, média
real do produto (4 fotos + vídeo de 30s validados), rastreio de transações, moderação em três
camadas com revisão humana, diagnóstico do sistema e interface responsiva.

### O que o plano gratuito permite, e o que não

A aplicação funciona sem geração de imagem: um anúncio com descrição, preço, contacto e fotos
reais do produto é um anúncio válido. A imagem gerada por IA é um extra, e a sua ausência é
mostrada e registada, nunca disfarçada.

Limites medidos no plano gratuito do Gemini:

- **Texto (legendas, descrições, moderação, categorias):** funciona, com **20 gerações por dia
  e por modelo** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`). Chega para uso real de
  demonstração, mas esgota-se depressa a testar.
- **Imagem:** `429` com `limit: 0` em **todos** os modelos de imagem — o plano gratuito não
  atribui qualquer quota. Seria preciso ativar faturação.
- **GMICloud (alternativa):** a chave é válida (78 modelos), mas devolve `402 Insufficient
  credits`.

Ambas as alternativas exigem um cartão de crédito ou débito internacional. O autor está em
Moçambique e não tem acesso a esse meio de pagamento: cartões pré-pagos não são aceites por
estes fornecedores, e o banco local não autoriza pagamentos online por cartão. Não é uma
decisão técnica nem uma tarefa por fazer — é uma barreira de acesso a infraestrutura, que é
precisamente o tipo de obstáculo que este projeto existe para contornar no lado de quem vende.

O comportamento perante essa falta foi verificado e é honesto: o post fica `failed` com a
mensagem real de cada provedor, sem estados presos nem sucessos simulados. Assim que existir
qualquer via de pagamento, a geração de imagem passa a funcionar sem alterar uma linha de
código — basta saldo. Confirma o estado de cada provedor em `/estado`.

**Por fazer:** deploy para a URL pública, conta de demonstração para os jurados e o vídeo de
apresentação.

**Nota sobre pagamentos:** o Boladas-ponto-com não processa nem retém dinheiro de
utilizadores. Um mecanismo desse tipo (custódia/escrow) exigiria licenciamento como
instituição de pagamento, o que está fora do âmbito deste MVP.
