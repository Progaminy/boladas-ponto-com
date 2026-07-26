#!/usr/bin/env python3
"""Grava um vídeo mudo da aplicação, para lhe pôr voz por cima.

Percorre a app num browser real e grava o que aparece no ecrã. Não há
narração nem legendas: o ficheiro resultante é só imagem, para ser montado
com a voz gravada à parte.

O ritmo é propositadamente lento — cada ecrã fica tempo suficiente para
alguém a narrar acompanhar sem ter de cortar o vídeo.

Uso:
    # 1. num terminal, com a app a correr:
    uvicorn app.main:app

    # 2. noutro terminal:
    python3 scripts/gravar_demo.py
    python3 scripts/gravar_demo.py --url http://127.0.0.1:8000 --saida demo/
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LARGURA, ALTURA = 1280, 720

# Conta de demonstração criada por scripts/seed_exemplos.py
EMAIL_DEMO = "ana@exemplo.boladas.mz"
PASSWORD_DEMO = "boladas2026"


def _pausa(segundos: float) -> None:
    """Tempo de leitura. Sem isto o vídeo passa depressa demais para narrar."""
    time.sleep(segundos)


def gravar(url_base: str, saida: Path, com_login: bool) -> Path | None:
    from playwright.sync_api import sync_playwright

    saida.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        contexto = navegador.new_context(
            viewport={"width": LARGURA, "height": ALTURA},
            record_video_dir=str(saida),
            record_video_size={"width": LARGURA, "height": ALTURA},
            locale="pt-PT",
        )
        pagina = contexto.new_page()

        def ir(caminho: str, espera: float = 3.0, titulo: str = "") -> None:
            print(f"  → {titulo or caminho}")
            try:
                pagina.goto(f"{url_base}{caminho}", wait_until="networkidle", timeout=20000)
            except Exception as exc:
                print(f"    (aviso: {str(exc)[:80]})")
            _pausa(espera)

        def rolar(passos: int = 3, pausa: float = 1.2) -> None:
            for _ in range(passos):
                pagina.mouse.wheel(0, 450)
                _pausa(pausa)

        print("A gravar:")

        # 1. Quem chega de fora: o que é a plataforma
        ir("/", 5, "Página de entrada")
        rolar(4)

        # 2. As regras do jogo
        ir("/termos", 4, "Termos de Uso")
        rolar(2)

        # 3. O diagnóstico honesto — testa mesmo as ligações
        ir("/estado", 6, "Estado do sistema (ligações reais)")
        rolar(2)

        if com_login:
            # 4. Entrar
            ir("/entrar", 2, "Entrar")
            try:
                # o campo aceita email ou telefone, conforme o formulário
                campo = "#identifier" if pagina.query_selector("#identifier") else "#email"
                pagina.fill(campo, EMAIL_DEMO)
                _pausa(0.8)
                pagina.fill("#password", PASSWORD_DEMO)
                _pausa(0.8)
                pagina.click("button[type=submit]")
                pagina.wait_for_load_state("networkidle", timeout=20000)
                _pausa(3)
            except Exception as exc:
                print(f"    (login falhou: {str(exc)[:90]})")

            # 5. O que já existe publicado
            ir("/explorar", 5, "Explorar negócios")
            rolar(4)

            # 6. Um anúncio concreto, com a proveniência
            try:
                pagina.click(".history-grid a, .feed-card a", timeout=5000)
                pagina.wait_for_load_state("networkidle", timeout=20000)
                _pausa(4)
                rolar(3)
                print("  → Post individual")

                # 7. A peça central: verificar contra o B2 ao vivo
                botao = pagina.query_selector("a[href$='/provenance']")
                if botao:
                    botao.click()
                    pagina.wait_for_load_state("networkidle", timeout=20000)
                    _pausa(3)
                    print("  → Proveniência")
                    verificar = pagina.query_selector("#verify-btn")
                    if verificar:
                        verificar.click()
                        print("  → Verificação ao vivo contra o Backblaze B2")
                        _pausa(9)  # a verificação vai mesmo buscar os ficheiros
                    rolar(3)
            except Exception as exc:
                print(f"    (aviso ao abrir post: {str(exc)[:90]})")

            # 8. Criar: é aqui que se vê o produto a trabalhar
            ir("/criar", 5, "Criar anúncio")
            rolar(3)

            # 9. Empresas e sócios
            ir("/empresa", 4, "As minhas empresas")
            rolar(2)

        video = pagina.video
        contexto.close()
        navegador.close()

        if video is None:
            return None
        return Path(video.path())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="URL da app a gravar")
    parser.add_argument("--saida", default="demo", help="pasta onde guardar o vídeo")
    parser.add_argument(
        "--sem-login", action="store_true", help="grava só as páginas públicas"
    )
    args = parser.parse_args()

    import httpx

    try:
        httpx.get(f"{args.url}/health", timeout=5)
    except Exception:
        print(
            f"Não consegui contactar {args.url}.\n"
            "Arranca a aplicação primeiro:  uvicorn app.main:app",
            file=sys.stderr,
        )
        return 2

    caminho = gravar(args.url, Path(args.saida), com_login=not args.sem_login)
    if caminho is None:
        print("A gravação não produziu ficheiro.", file=sys.stderr)
        return 1

    destino = Path(args.saida) / "boladas-demo.webm"
    caminho.replace(destino)
    tamanho = destino.stat().st_size / 1024 / 1024
    print(f"\nVídeo mudo: {destino}  ({tamanho:.1f} MB)")
    print("Junta a tua narração por cima, por exemplo:")
    print(f"  ffmpeg -i {destino} -i voz.mp3 -c:v copy -shortest demo-final.webm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
