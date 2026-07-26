const form = document.getElementById("post-form");
const banner = document.getElementById("status-banner");
const submitBtn = document.getElementById("submit-btn");

function setBanner(status, text) {
  banner.className = `status-banner visible ${status}`;
  banner.textContent = text;
}

if (form) {
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    submitBtn.disabled = true;
    // A app não simula progresso: mostra "a gerar" até o backend responder
    // com o resultado real (sucesso ou falha).
    setBanner("generating", "A gerar imagem, legenda e hashtags com o Genblaze/GMICloud... isto pode demorar até 1-2 minutos.");

    const formData = new FormData(form);
    try {
      const resp = await fetch("/posts", { method: "POST", body: formData });
      const data = await resp.json();

      if (resp.ok && data.status === "completed") {
        // Um post pode concluir-se sem imagem gerada. Dizê-lo aqui evita que
        // a pessoa descubra a ausência só na página seguinte.
        setBanner(
          "completed",
          data.image_skipped_reason
            ? "Post criado e guardado no Backblaze B2 — sem imagem gerada (o texto está lá). A redirecionar..."
            : "Post gerado e armazenado no Backblaze B2 com sucesso. A redirecionar..."
        );
        window.location.href = `/posts/${data.post_id}`;
      } else {
        setBanner("failed", `Falhou: ${data.error || "erro desconhecido"}`);
        submitBtn.disabled = false;
      }
    } catch (err) {
      setBanner("failed", `Erro de rede: ${err}`);
      submitBtn.disabled = false;
    }
  });
}

// --- descrição do produto: escrita à mão, ou gerada pela IA a partir de uma
// foto real ou de uma explicação informal ---
const describeBtn = document.getElementById("describe-btn");
const describeStatus = document.getElementById("describe-status");
const descriptionField = document.getElementById("description");
const descriptionSource = document.getElementById("description_source");

if (describeBtn) {
  // se a pessoa editar o texto depois de a IA o gerar, passa a contar como
  // escrito por ela — a origem registada tem de corresponder ao que é verdade
  descriptionField.addEventListener("input", () => {
    if (descriptionSource.value.startsWith("ia_")) descriptionSource.value = "manual";
  });

  describeBtn.addEventListener("click", async () => {
    const explicacao = document.getElementById("explicacao").value.trim();
    const foto = document.getElementById("foto_descricao").files[0];

    if (!explicacao && !foto) {
      describeStatus.textContent = "Escreve uma explicação ou envia uma foto.";
      describeStatus.className = "describe-status failed";
      return;
    }

    describeBtn.disabled = true;
    describeStatus.className = "describe-status working";
    describeStatus.textContent = foto
      ? "A olhar para a foto..."
      : "A escrever a descrição...";

    const dados = new FormData();
    if (explicacao) dados.append("explicacao", explicacao);
    if (foto) dados.append("foto", foto);

    try {
      const resp = await fetch("/descricao/sugerir", { method: "POST", body: dados });
      const data = await resp.json();
      if (resp.ok) {
        descriptionField.value = data.description;
        descriptionSource.value = data.source;
        describeStatus.className = "describe-status ok";
        describeStatus.textContent =
          data.source === "ia_foto"
            ? "Descrição escrita a partir da foto. Podes editá-la."
            : "Descrição escrita pela IA. Podes editá-la.";
      } else {
        describeStatus.className = "describe-status failed";
        describeStatus.textContent = data.error || "Não foi possível gerar.";
      }
    } catch (err) {
      describeStatus.className = "describe-status failed";
      describeStatus.textContent = `Erro de rede: ${err}`;
    }
    describeBtn.disabled = false;
  });
}
