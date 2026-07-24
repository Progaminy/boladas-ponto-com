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
        setBanner("completed", "Post gerado e armazenado no Backblaze B2 com sucesso. A redirecionar...");
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
