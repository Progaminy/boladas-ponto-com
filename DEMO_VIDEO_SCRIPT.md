# Roteiro do vídeo de demonstração — Boladas-ponto-com

**Vídeo:** `demo/boladas-demo.webm`
**Duração real:** 1 minuto e 58,96 segundos
**Formato:** 1280 × 720, WebM, sem áudio
**Cliques destacados:** 13 de 13, todos com seta amarela

Os tempos seguem a gravação com tolerância aproximada de meio segundo para
as transições entre páginas.

## Narração sincronizada

### 0:00–0:13 — Apresentação pública

**Visual:** marca “Boladas-ponto-com”, slogan “Do zero ao infinito.”,
explicação do funcionamento, princípio “Nunca fingir”, categorias e confiança
entre comprador e vendedor.

**Narração:**

> Este é o Boladas-ponto-com. Do zero ao infinito. Antes do login, a página pública apresenta a proposta: criar anúncios com inteligência artificial e conservar uma origem verificável no Backblaze B2.

### 0:13–0:22.5 — Termos e entrada

**Visual:** seta em “Termos de Uso”, leitura da página e seta no link “Entrar”.

**Narração:**

> Abrimos os Termos de Uso, que explicam responsabilidades, conteúdo permitido e pagamentos diretos. Depois selecionamos Entrar.

### 0:22.5–0:35 — Autenticação

**Visual:** setas no campo de email, no campo da password e no botão “Entrar”.

**Narração:**

> No formulário, indicamos o email e a password da conta de demonstração. O feed só é aberto depois da autenticação.

### 0:35–0:54.5 — Feed autenticado

**Visual:** feed completo da utilizadora Ana Machava, filtros, cartões, interações
e navegação privada; no fim, seta em “Comparar Preços & GPS”.

**Narração:**

> Agora, autenticada como Ana Machava, a conta mostra o feed completo, com filtros, preços, localização, reações, comentários e opções privadas para anunciar, gerir empresas, mensagens e transações. Em seguida, abrimos o comparador.

### 0:54.5–1:03.7 — Pesquisa por cimento

**Visual:** seta no campo de pesquisa, texto “Cimento”, coordenadas de Maputo e
seta no botão “Comparar Preços”.

**Narração:**

> Pesquisamos por cimento, mantemos a ordenação por menor preço e usamos coordenadas de Maputo para calcular proximidade.

### 1:03.7–1:11.2 — Resultados

**Visual:** cimento por 480 MT e 620 MT; transporte de materiais por 2.500 MT;
distância GPS em parte das ofertas.

**Narração:**

> Cimento custa 480 e 620 Meticais; transporte, 2.500. Algumas ofertas exibem distância GPS.

### 1:11.2–1:18.5 — Voltar ao feed e abrir anúncio

**Visual:** seta em “Voltar ao Feed”, retorno aos cartões e seta em
“Ver Anúncio” no Samsung A12.

**Narração:**

> Voltamos ao feed autenticado e abrimos o anúncio do Telemóvel Usado Samsung A12.

### 1:18.5–1:31 — Detalhes do anúncio

**Visual:** anúncio concluído do Samsung A12, descrição, preço de 6.500 MT,
contacto, assistência, comentários e seta em “Ver Proveniência B2”.

**Narração:**

> O anúncio apresenta descrição, preço de 6.500 Meticais, contacto, assistência e comentários. Depois escolhemos Ver Proveniência B2.

### 1:31–1:40.7 — Tentativa de obter a proveniência

**Visual:** pedido de `provenance.json` ao Backblaze B2, erro real
`Key not found` e seta em “Anunciar”.

**Narração:**

> A aplicação procura o manifesto no Backblaze B2. Neste ambiente, o objeto não existe; o erro Key not found aparece sem simular sucesso.

### 1:40.7–1:52.3 — Formulário para anunciar

**Visual:** formulário de criação, sem submissão; no fim, seta em
“Minhas empresas”.

**Narração:**

> Em Anunciar, o formulário recolhe produto, descrição, preço, localização e contacto, sem publicar nada nesta demonstração. Depois abrimos Minhas empresas.

### 1:52.3–1:58.96 — Empresa da conta

**Visual:** “Farmácia Vida Nova”, com os links “Ver perfil” e “Editar”.

**Narração:**

> A conta mostra a Farmácia Vida Nova, com opções para ver o perfil e editar.

## Texto curto para a descrição do vídeo

> Demonstração do Boladas-ponto-com: apresentação pública antes do login, feed e comparador protegidos por autenticação, comparação de preços com GPS, anúncio Samsung A12, tentativa transparente de obter a proveniência no Backblaze B2, formulário de publicação e gestão de empresa. Uma seta amarela identifica cada clique.

## Nota de edição

O vídeo foi gravado sem áudio. Para juntar uma faixa chamada `voz.mp3`:

```bash
ffmpeg -i demo/boladas-demo.webm -i voz.mp3 \
  -c:v copy -c:a libopus -shortest demo/boladas-demo-narrado.webm
```
