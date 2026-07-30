#!/usr/bin/env python3
"""Cria contas reais pela interface web e envia fotos de perfil e capa.

Usa um browser verdadeiro (Playwright) para preencher os mesmos formulários
que uma pessoa preencheria — não escreve na base de dados por atalho. As
fotos passam pelo fluxo real de upload e ficam no Backblaze B2, com o SHA-256
verificado depois do envio.

As imagens são lidas de `fotos/` (pasta fora do git, por peso). Se faltarem,
o script diz o que falta em vez de inventar imagens.

Uso:
    # com a app a correr e o B2 configurado no .env:
    python3 scripts/criar_contas_com_fotos.py
    python3 scripts/criar_contas_com_fotos.py --url http://127.0.0.1:8000
"""

import argparse
import sys
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

PASTA_FOTOS = RAIZ / "fotos"
PASSWORD = "boladas2026"

# Cada conta usa um par de imagens diferente, para os perfis não ficarem iguais.
CONTAS = [
    {"nome": "Amélia Tembe", "local": "amelia", "perfil": "perfil-1.jpg", "capa": "capa-1.jpg"},
    {"nome": "Custódio Mabote", "local": "custodio", "perfil": "perfil-2.jpg", "capa": "capa-2.jpg"},
    {"nome": "Felismina Chirindza", "local": "felismina", "perfil": "perfil-3.jpg", "capa": "capa-3.jpg"},
    {"nome": "Gerson Matola", "local": "gerson", "perfil": "perfil-4.jpg", "capa": "capa-4.jpg"},
]

SUFIXO = "@exemplo.boladas.mz"


def _validar_fotos() -> list[str]:
    faltam = []
    for conta in CONTAS:
        for chave in ("perfil", "capa"):
            caminho = PASTA_FOTOS / conta[chave]
            if not caminho.exists():
                faltam.append(str(caminho.relative_to(RAIZ)))
    return faltam


def criar(url_base: str) -> int:
    from playwright.sync_api import sync_playwright

    from app import db

    criadas = 0
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        for conta in CONTAS:
            # sufixo aleatório: permite correr várias vezes sem colidir com
            # contas já existentes, mantendo o domínio de exemplo
            email = f"{conta['local']}.{uuid.uuid4().hex[:6]}{SUFIXO}"
            contexto = navegador.new_context(
                viewport={"width": 1280, "height": 900}, locale="pt-PT"
            )
            pagina = contexto.new_page()
            print(f"\n{conta['nome']}  <{email}>")

            try:
                # 1. registo pelo formulário real
                pagina.goto(f"{url_base}/registar", wait_until="networkidle", timeout=25000)
                pagina.fill("#display_name", conta["nome"])
                pagina.fill("#email", email)
                pagina.fill("#password", PASSWORD)
                pagina.check("input[name=terms_accepted]")
                pagina.click("form[action='/registar'] button[type=submit]")
                pagina.wait_for_load_state("networkidle", timeout=25000)
                print("  conta criada")

                # 2. fotos de perfil e capa pelo formulário real
                pagina.goto(f"{url_base}/perfil/fotos", wait_until="networkidle", timeout=25000)
                pagina.set_input_files("#profile_photo", str(PASTA_FOTOS / conta["perfil"]))
                pagina.set_input_files("#cover_photo", str(PASTA_FOTOS / conta["capa"]))
                pagina.click("form[enctype='multipart/form-data'] button[type=submit]")
                pagina.wait_for_load_state("networkidle", timeout=60000)
                print(f"  fotos enviadas ({conta['perfil']}, {conta['capa']})")

                # 3. confirmar que ficaram guardadas de verdade
                utilizador = db.get_user_by_email(email)
                if utilizador is None:
                    print("  AVISO: conta não encontrada na base de dados")
                    continue
                chaves = [utilizador["profile_photo_key"], utilizador["cover_photo_key"]]
                if all(chaves):
                    print(f"  no B2: {chaves[0]}")
                    print(f"         {chaves[1]}")
                    criadas += 1
                else:
                    print(f"  AVISO: fotos não registadas (chaves={chaves})")
            except Exception as exc:
                print(f"  falhou: {str(exc)[:140]}")
            finally:
                contexto.close()
        navegador.close()
    return criadas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    faltam = _validar_fotos()
    if faltam:
        print("Faltam imagens em fotos/ (pasta fora do git):", file=sys.stderr)
        for f in faltam:
            print(f"  {f}", file=sys.stderr)
        return 2

    import httpx

    try:
        saude = httpx.get(f"{args.url}/health", timeout=10).json()
    except Exception:
        print(f"A app não responde em {args.url}. Arranca-a primeiro.", file=sys.stderr)
        return 2
    if not saude.get("b2_configured"):
        print(
            "O Backblaze B2 não está configurado nesta instância — as fotos não\n"
            "seriam guardadas. Carrega o .env antes de arrancar a app.",
            file=sys.stderr,
        )
        return 2

    criadas = criar(args.url)
    print(f"\n{criadas}/{len(CONTAS)} contas com fotos confirmadas no Backblaze B2.")
    return 0 if criadas else 1


if __name__ == "__main__":
    raise SystemExit(main())
