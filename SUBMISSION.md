# Boladas-ponto-com — Dossier de Submissão

**Backblaze Generative Media Hackathon**  
**Projeto**: Boladas-ponto-com — Plataforma de Geração de Anúncios, Comércio Local, Proveniência Digital e Comparação de Preços com GPS  
**Slogan**: *Crie posts. Guarde a origem. Conecte negócios em Moçambique.*

---

## 🚀 Resumo Executivo

O **Boladas-ponto-com** é uma aplicação completa de geração de conteúdos publicitários e comércio local desenvolvida para o mercado moçambicano. A plataforma transforma dados básicos de produtos e serviços em posts publicitários prontos a publicar (imagem 1080×1080, legenda, hashtags e botões de ação), associando a cada publicação um **manifesto de proveniência criptográfica (SHA-256)** armazenado no **Backblaze B2**.

A plataforma serve tanto vendedores individuais como empresas físicas (Farmácias, Ferragens, Boutiques, Mercados Populares e Serviços de Transporte), oferecendo um **Feed Social estilo Facebook/TikTok**, **Diretório Público de Empresas**, **Comparador de Preços em Meticais (MT) com Deteção de Proximidade Física via GPS** e **Messenger com Mediação da Plataforma (872599084)**.

---

## 🛠️ Arquitetura & Integração Backblaze B2

### 1. SDK Genblaze & Armazenamento B2
- **SDK Utilizado**: [`genblaze-core`](https://pypi.org/project/genblaze-core/), `genblaze-gmicloud`, `genblaze-s3`.
- **Bucket**: `pensador-sem-fronteiras-media` (Região: `us-east-005`).
- **Estrutura de Ficheiros no B2**:
  ```text
  posts/<post_id>/
  ├── image.png          (Imagem final 1080x1080 com overlay de preço e CTA)
  ├── caption.txt        (Legenda publicitária gerada + hashtags)
  ├── provenance.json    (Manifesto de proveniência com hashes SHA-256 e metadata)
  └── thumbnail.webp     (Miniatura otimizada para o feed)
  ```

### 2. Princípio "Nunca Fingir" & Verificação ao Vivo
- **Verificação SHA-256 no Upload**: Após a transferência para o Backblaze B2, a aplicação descarrega os bytes de volta e compara o hash SHA-256 calculado localmente contra os bytes remotos confirmados.
- **Página de Verificação de Proveniência em Tempo Real (`POST /posts/{id}/verificar`)**: Qualquer visitante (sem necessidade de conta) pode clicar no botão *Verificar contra o Backblaze B2 agora*. A aplicação descarrega novamente cada objeto do bucket e confirma a integridade dos ficheiros em tempo real.
- **Página de Diagnóstico do Sistema (`/estado`)**: Executa verificações reais de ligação ao Backblaze B2, Vertex AI Express e GMICloud.

---

## 🤖 Resiliência & Provedores de Inteligência Artificial

A plataforma utiliza um pipeline multi-provider resiliente:
- **Provedor Principal**: **Gemini via Vertex AI Express** (`gemini-2.5-flash-image` para imagem, `gemini-2.5-flash` para legenda e moderação visual).
- **Provedor Fallback**: **GMICloud** (`seedream-5.0-lite` para imagem, `DeepSeek-V3` para texto).
- **Resiliência contra Quota Exaurida (HTTP 429)**: Se os provedores de IA excederem o limite gratuito (`429 RESOURCE_EXHAUSTED`), a publicação **nunca falha**. O sistema ativa a legenda de recurso com base no briefing do utilizador, realiza a composição determinística com Pillow e armazena com sucesso os ficheiros no Backblaze B2 com estado `completed`.

---

## ✨ Funcionalidades em Destaque

1. **Diretório Público de Empresas (`/empresas`)**:
   - Páginas completas com capas, logótipos, NUIT, localização, catálogo de produtos e gestores de lojas reais (ex.: *Farmácia Moçambique Vida, Ferragem Lendária Maputo, Moda & Estilo Boutique, Mercado Popular de Xipamanine, Transporte & Carga Expresso*).
2. **Comparador de Preços & GPS Proximidade (`/comparar`)**:
   - Comparação de preços em Meticais (`MT`) e integração com a API `navigator.geolocation` do navegador para calcular a distância exata em quilómetros (`🚗 1.2 km de distância`) até à loja física mais próxima.
3. **Feed Social & Interação Completa (`/explorar` e `/`)**:
   - Cartões com foto de perfil/avatar, reações (👍 Like / 👎 Dislike com motivo auditável) e caixas de comentários públicas.
4. **Messenger Boladas & Mediação Humana (`872599084`)**:
   - Ficha de contexto do produto no topo do chat e botão `🆘 Pedir Assistência Humana` para apoio direto da equipa da plataforma.
5. **Autonomia & Temas Festivos (`/perfil/fotos` e `/empresa/{id}`)**:
   - Controlo total para alterar fotos, editar anúncios e ativar temas festivos (Natal, Festas de Empresa).
6. **Moderação em 3 Camadas**:
   - (1) Lista de palavras proibidas local; (2) Moderação textual por IA; (3) Moderação visual de imagens/vídeos com o Gemini.

---

## ⚙️ Instruções de Instalação e Execução

### 1. Clonar e Instalar Dependências
```bash
git clone https://github.com/Progaminy/boladas-ponto-com.git
cd boladas-ponto-com
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configurar Variáveis de Ambiente (`.env`)
```dotenv
B2_KEY_ID=sua_chave_id_backblaze
B2_APP_KEY=sua_chave_aplicacao_backblaze
B2_BUCKET=pensador-sem-fronteiras-media
B2_REGION=us-east-005

AI_PROVIDER=auto
VERTEX_EXPRESS_API_KEY=sua_chave_vertex_express
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image
GEMINI_CHAT_MODEL=gemini-2.5-flash
GMI_API_KEY=sua_chave_gmicloud
```

### 3. Iniciar a Aplicação
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Acede a `http://localhost:8000` no teu navegador.

### 4. Executar Testes Automatizados
```bash
pytest -v
```
Todos os 115+ testes devem passar com sucesso (`100% pass`).

---

## 📌 Links Importantes
- **Repositório GitHub**: [https://github.com/Progaminy/boladas-ponto-com](https://github.com/Progaminy/boladas-ponto-com)
- **Diagnóstico do Sistema**: `http://localhost:8000/estado`
- **Diretório de Lojas**: `http://localhost:8000/empresas`
- **Comparador de Preços & GPS**: `http://localhost:8000/comparar`
