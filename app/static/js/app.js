const form = document.getElementById("post-form");
const banner = document.getElementById("status-banner");
const submitBtn = document.getElementById("submit-btn");
const postPhotosInput = document.getElementById("post_photos");
const photoPreview = document.getElementById("post-photo-preview");

const MAX_PRODUCT_PHOTOS = 2;
const MAX_PHOTO_BYTES = 8 * 1024 * 1024;
const ALLOWED_PHOTO_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function setBanner(status, text) {
  if (!banner) return;
  banner.className = `status-banner visible ${status}`;
  banner.textContent = text;
}

function selectedProductPhotos() {
  return postPhotosInput ? Array.from(postPhotosInput.files || []) : [];
}

function validateSelectedPhotos(photos) {
  if (photos.length < 1) return "Adiciona pelo menos 1 foto do produto.";
  if (photos.length > MAX_PRODUCT_PHOTOS) return "Escolhe no máximo 2 fotos por produto.";

  for (const photo of photos) {
    if (!ALLOWED_PHOTO_TYPES.has(photo.type)) {
      return "Usa apenas fotos JPG, PNG ou WebP.";
    }
    if (photo.size > MAX_PHOTO_BYTES) {
      return `A foto ${photo.name} ultrapassa o limite de 8 MB.`;
    }
  }
  return null;
}

function renderPhotoPreview() {
  if (!postPhotosInput || !photoPreview) return;
  const photos = selectedProductPhotos();
  photoPreview.innerHTML = "";

  const error = validateSelectedPhotos(photos);
  if (error && photos.length) {
    setBanner("failed", error);
    if (photos.length > MAX_PRODUCT_PHOTOS) postPhotosInput.value = "";
    return;
  }

  photos.forEach((photo, index) => {
    const wrapper = document.createElement("div");
    wrapper.style.width = "96px";
    wrapper.style.textAlign = "center";

    const img = document.createElement("img");
    const objectUrl = URL.createObjectURL(photo);
    img.src = objectUrl;
    img.alt = `Pré-visualização da foto ${index + 1}`;
    img.style.width = "96px";
    img.style.height = "96px";
    img.style.objectFit = "cover";
    img.style.borderRadius = "10px";
    img.style.border = index === 0 ? "2px solid #7C3AED" : "1px solid #374151";
    img.addEventListener("load", () => URL.revokeObjectURL(objectUrl), { once: true });

    const label = document.createElement("small");
    label.textContent = index === 0 ? "Foto principal" : "Foto 2";
    label.style.display = "block";
    label.style.marginTop = "0.2rem";

    wrapper.appendChild(img);
    wrapper.appendChild(label);
    photoPreview.appendChild(wrapper);
  });
}

if (postPhotosInput) postPhotosInput.addEventListener("change", renderPhotoPreview);

async function uploadPostPhotos(postId, photos) {
  const data = new FormData();
  photos.forEach((photo) => data.append("photos", photo));
  return fetch(`/posts/${postId}/media`, { method: "POST", body: data });
}

if (form) {
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();

    const photos = selectedProductPhotos();
    const photoError = validateSelectedPhotos(photos);
    if (photoError) {
      setBanner("failed", photoError);
      return;
    }

    const themeInput = document.getElementById("theme");
    const businessInput = document.getElementById("business");
    if (themeInput && businessInput && !themeInput.value.trim()) {
      themeInput.value = businessInput.value.trim();
    }

    submitBtn.disabled = true;
    setBanner("generating", "A publicar o anúncio...");

    const formData = new FormData(form);
    formData.delete("post_photos");

    try {
      const resp = await fetch("/posts", { method: "POST", body: formData });
      const data = await resp.json();

      if (resp.ok && data.status === "completed") {
        setBanner(
          "generating",
          `Anúncio criado. A guardar ${photos.length} foto${photos.length === 1 ? "" : "s"}...`
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
          `Anúncio publicado com ${photos.length} foto${photos.length === 1 ? "" : "s"}.`
        );
        window.setTimeout(() => {
          window.location.href = `/posts/${data.post_id}`;
        }, 500);
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
