const form = document.getElementById("post-form");
const banner = document.getElementById("status-banner");
const submitBtn = document.getElementById("submit-btn");

function setBanner(status, text) {
  banner.className = `status-banner visible ${status}`;
  banner.textContent = text;
}

let postPhotosInput = null;
let photoPreview = null;

function installPostPhotoPicker() {
  if (!form || !submitBtn || document.getElementById("post_photos")) return;

  const box = document.createElement("fieldset");
  box.className = "describe-box";
  box.innerHTML = `
    <legend>Fotos do anúncio</legend>
    <p class="muted describe-hint">
      Podes publicar com fotos reais do produto. Escolhe até 4 imagens da galeria
      ou da câmara. A primeira foto será usada como imagem principal do anúncio.
    </p>
    <div class="field">
      <label for="post_photos">Adicionar fotos</label>
      <input type="file" id="post_photos"
             accept="image/jpeg,image/png,image/webp" multiple />
      <p class="muted" style="margin:0.35rem 0 0; font-size:0.85rem;">
        Máximo: 4 fotos, 8 MB por foto. JPG, PNG ou WebP.
      </p>
    </div>
    <div id="post-photo-preview" style="display:flex; gap:0.55rem; flex-wrap:wrap;"></div>
  `;

  const advanced = document.getElementById("advanced-options");
  if (advanced) {
    advanced.insertAdjacentElement("beforebegin", box);
  } else {
    submitBtn.insertAdjacentElement("beforebegin", box);
  }

  postPhotosInput = document.getElementById("post_photos");
  photoPreview = document.getElementById("post-photo-preview");

  postPhotosInput.addEventListener("change", () => {
    const photos = Array.from(postPhotosInput.files || []);
    photoPreview.innerHTML = "";

    if (photos.length > 4) {
      setBanner("failed", "Escolhe no máximo 4 fotos por anúncio.");
      postPhotosInput.value = "";
      return;
    }

    photos.forEach((photo, index) => {
      const wrapper = document.createElement("div");
      wrapper.style.width = "82px";
      wrapper.style.textAlign = "center";

      const img = document.createElement("img");
      img.src = URL.createObjectURL(photo);
      img.alt = `Pré-visualização da foto ${index + 1}`;
      img.style.width = "82px";
      img.style.height = "82px";
      img.style.objectFit = "cover";
      img.style.borderRadius = "10px";
      img.style.border = index === 0 ? "2px solid #7C3AED" : "1px solid #374151";
      img.addEventListener("load", () => URL.revokeObjectURL(img.src), { once: true });

      const label = document.createElement("small");
      label.textContent = index === 0 ? "Principal" : `Foto ${index + 1}`;
      label.style.display = "block";
      label.style.marginTop = "0.2rem";

      wrapper.appendChild(img);
      wrapper.appendChild(label);
      photoPreview.appendChild(wrapper);
    });
  });
}

async function uploadPostPhotos(postId, photos) {
  const data = new FormData();
  photos.forEach((photo) => data.append("photos", photo));
  return fetch(`/posts/${postId}/media`, { method: "POST", body: data });
}

installPostPhotoPicker();

if (form) {
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();

    const photos = postPhotosInput ? Array.from(postPhotosInput.files || []) : [];
    if (photos.length > 4) {
      setBanner("failed", "Escolhe no máximo 4 fotos por anúncio.");
      return;
    }

    submitBtn.disabled = true;
    setBanner(
      "generating",
      photos.length
        ? `A criar o anúncio. Depois vou enviar ${photos.length} foto${photos.length === 1 ? "" : "s"}...`
        : "A gerar imagem, legenda e hashtags com o Genblaze/GMICloud... isto pode demorar até 1-2 minutos."
    );

    const formData = new FormData(form);
    try {
      const resp = await fetch("/posts", { method: "POST", body: formData });
      const data = await resp.json();

      if (resp.ok && data.status === "completed") {
        if (photos.length) {
          setBanner(
            "generating",
            `Anúncio criado. A guardar ${photos.length} foto${photos.length === 1 ? "" : "s"} no Backblaze B2...`
          );
          const mediaResp = await uploadPostPhotos(data.post_id, photos);
          if (!mediaResp.ok) {
            setBanner(
              "failed",
              "O anúncio foi criado, mas não consegui guardar as fotos. Vou abrir a página para tentares novamente."
            );
            window.setTimeout(() => {
              window.location.href = `/posts/${data.post_id}/media`;
            }, 900);
            return;
          }

          setBanner(
            "completed",
            `${photos.length} foto${photos.length === 1 ? "" : "s"} guardada${photos.length === 1 ? "" : "s"}. Anúncio publicado com sucesso.`
          );
          window.setTimeout(() => {
            window.location.href = `/posts/${data.post_id}`;
          }, 500);
          return;
        }

        // Um post pode concluir-se sem imagem gerada. Dizê-lo aqui evita que
        // a pessoa descubra a ausência só na página seguinte.
        setBanner(
          "completed",
          data.image_skipped_reason
            ? "Anúncio publicado e guardado no Backblaze B2. A imagem fica a aguardar disponibilidade da IA — o resto do anúncio está completo. A redirecionar..."
            : "Post gerado e armazenado no Backblaze B2 com sucesso. A redirecionar..."
        );
        window.location.href = `/perfil?tab=produtos&created=${data.post_id}#produtos`;
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
