# Roteiro do Vídeo de Demonstração — Boladas-ponto-com

**Duração Estimada**: ~2 minutos e 30 segundos a 3 minutos  
**Objetivo**: Apresentar aos jurados do **Backblaze Generative Media Hackathon** o funcionamento prático da aplicação, a integração profunda com o **Backblaze B2**, o **SDK Genblaze**, a resiliência de IA e a proveniência verificável.

---

## 🎬 Visão Geral do Roteiro

| Cenas | Tempo | Foco Principal |
| :--- | :--- | :--- |
| **Cena 1: Introdução & Problema** | 0:00 - 0:25 | Apresentação do projeto e contexto do comércio em Moçambique |
| **Cena 2: Feed Social & Lojas Reais** | 0:25 - 0:55 | Navegação no Feed (`/explorar`) e Diretório de Empresas (`/empresas`) |
| **Cena 3: Comparador de Preços com GPS** | 0:55 - 1:25 | Deteção de proximidade física e comparação em Meticais (`/comparar`) |
| **Cena 4: Geração de Post & Genblaze SDK** | 1:25 - 1:55 | Criação do anúncio com Gemini Vertex AI + composição determinística |
| **Cena 5: Proveniência B2 & Diagnóstico** | 1:55 - 2:25 | Verificação SHA-256 ao vivo no Backblaze B2 e `/estado` |
| **Cena 6: Conclusão & Call to Action** | 2:25 - 2:40 | Encerramento e links para o repositório |

---

## 📜 Roteiro Detalhado (Cena por Cena)

### 🎬 Cena 1: Introdução & Apresentação (0:00 - 0:25)
- **Visual**: Ecrã inicial da plataforma `http://localhost:8000/` com o logo e slogan *"Crie posts. Guarde a origem."*
- **Texto no Ecrã (Overlay)**: `Boladas-ponto-com | Backblaze Generative Media Hackathon`
- **Voz de Narração**:
  > *"Olá a todos! Este é o Boladas-ponto-com, uma plataforma de geração de posts publicitários, comércio local e proveniência digital criada para o Backblaze Generative Media Hackathon.*
  > *Em Moçambique, pequenas empresas e vendedores locais precisam de criar anúncios atraentes para redes sociais, mas com a garantia de que as suas marcas e conteúdos são autênticos e verificáveis."*

---

### 🎬 Cena 2: Feed Social & Diretório de Empresas (0:25 - 0:55)
- **Visual**: Scroll pelo Feed Social (`/explorar`), mostrando cartões com fotos, avatares, reações (👍 / 👎) e botões de contacto. Depois, clique em `🏢 Lojas & Empresas` (`/empresas`).
- **Texto no Ecrã (Overlay)**: `Feed Social & Montras de Empresas Reais`
- **Voz de Narração**:
  > *"Ao entrar na aplicação, os utilizadores navegam diretamente num Feed Social dinâmico estilo Facebook. No Diretório de Empresas, encontramos montras profissionais de negócios reais, como a Farmácia Moçambique Vida, Ferragem Lendária Maputo, Moda & Estilo e Mercado Popular de Xipamanine — cada uma com capa, logótipo, NUIT, catálogo de produtos e gestores registados."*

---

### 🎬 Cena 3: Comparador de Preços & GPS Proximidade (0:55 - 1:25)
- **Visual**: Aceder a `/comparar`, escrever "Cimento" no campo de busca e clicar no botão `📡 Usar Minha Localização GPS`. Mostrar a ordenação por distância (`🚗 1.2 km de distância`) e menor preço em Meticais (`MT`).
- **Texto no Ecrã (Overlay)**: `Comparador de Preços em MT + GPS Proximidade (Fórmula Haversine)`
- **Voz de Narração**:
  > *"Na secção Comparar Preços, qualquer comprador pode pesquisar por um produto — como Cimento ou Paracetamol — e ativar a Geolocalização GPS do seu telemóvel.*
  > *A aplicação calcula instantaneamente a distância exata em quilómetros até à loja física mais próxima e ordena pelos menores preços em Meticais, facilitando compras presenciais imediatas."*

---

### 🎬 Cena 4: Criar Post com IA & Genblaze SDK (1:25 - 1:55)
- **Visual**: Aceder a `/postar`, preencher o briefing (Produto: "Saco de Cimento Limpopo 50kg", Preço: "650 MT", Categoria: "Ferragem"). Clicar em `Gerar com IA`. Mostrar a barra de progresso e o resultado final com a imagem 1080×1080 composta com Pillow.
- **Texto no Ecrã (Overlay)**: `Genblaze SDK + Gemini Vertex AI Express + Pillow Overlay`
- **Voz de Narração**:
  > *"Ao criar um post, o nosso motor utiliza o SDK oficial Genblaze com o Gemini Vertex AI Express como provedor principal e GMICloud como fallback. Se a quota de IA for atingida, a nossa arquitetura resiliente completa o post sem nunca bloquear a publicação, sobrepondo o preço e a chamada para ação com Pillow."*

---

### 🎬 Cena 5: Verificação de Proveniência ao Vivo no Backblaze B2 (1:55 - 2:25)
- **Visual**: Na página do post gerado, clicar no separador *Verificar Proveniência*. Clicar no botão `Verificar contra o Backblaze B2 agora`. Mostrar a verificação verde dos hashes SHA-256 (`image.png`, `caption.txt`, `provenance.json`). Abrir rapidamente `/estado` para mostrar a saúde real dos serviços.
- **Texto no Ecrã (Overlay)**: `Verificação Criptográfica SHA-256 em Tempo Real no Backblaze B2`
- **Voz de Narração**:
  > *"A nossa garantia é o princípio 'Nunca Fingir'. No Backblaze B2, guardamos a imagem, a legenda e o manifesto de proveniência com SHA-256. Qualquer pessoa pode clicar em 'Verificar contra o Backblaze B2 agora' e a aplicação descarrega os bytes do bucket em tempo real para auditabilidade total."*

---

### 🎬 Cena 6: Conclusão & Encerramento (2:25 - 2:40)
- **Visual**: Mostrar a página inicial com links para a documentação e o repositório GitHub `github.com/Progaminy/boladas-ponto-com`.
- **Texto no Ecrã (Overlay)**: `Obrigado! Repositório: github.com/Progaminy/boladas-ponto-com`
- **Voz de Narração**:
  > *"O Boladas-ponto-com traz transparência, inteligência artificial e comércio local de alto impacto para Moçambique com a infraestrutura robusta do Backblaze B2. Muito obrigado!"*

---

## 🎥 Dicas Rápidas para a Gravação
1. **Ferramenta de Gravação**: Podes usar **OBS Studio**, **Loom** ou a gravação nativa do sistema operativo (1080p).
2. **Áudio**: Grava a narração com um microfone claro e sem ruído de fundo.
3. **Navegador**: Abre em modo de ecrã inteiro (F11) ou janela limpa para destacar a interface visual.
