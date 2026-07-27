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

        cliques_com_seta: list[str] = []

        def apontar_e_clicar(
            seletor: str, descricao: str, espera: float = 1.8
        ) -> None:
            """Mostra uma seta inteira no alvo e só depois executa o clique."""
            alvo = pagina.locator(seletor).first
            alvo.scroll_into_view_if_needed()
            _pausa(0.45)
            caixa = alvo.bounding_box()
            if caixa is None:
                raise RuntimeError(f"elemento sem posição visível: {seletor}")
            x = caixa["x"] + caixa["width"] / 2
            y = caixa["y"] + caixa["height"] / 2
            pagina.evaluate(
                """({x, y, descricao}) => {
                    document.getElementById('demo-click-arrow')?.remove();
                    const wrap = document.createElement('div');
                    wrap.id = 'demo-click-arrow';
                    wrap.setAttribute('aria-hidden', 'true');
                    Object.assign(wrap.style, {
                        position: 'fixed',
                        inset: '0',
                        zIndex: '2147483647',
                        pointerEvents: 'none',
                        width: '100vw',
                        height: '100vh'
                    });

                    const margem = 115;
                    let sx;
                    let sy;
                    if (y < 145) {
                        sx = Math.min(window.innerWidth - margem, Math.max(margem, x + 120));
                        sy = y + 115;
                    } else if (y > window.innerHeight - 145) {
                        sx = Math.min(window.innerWidth - margem, Math.max(margem, x - 120));
                        sy = y - 115;
                    } else {
                        sx = x > window.innerWidth / 2 ? x - 125 : x + 125;
                        sy = y - 90;
                    }
                    const cx = (sx + x) / 2;
                    const cy = (sy + y) / 2 - 24;
                    const labelX = Math.min(
                        window.innerWidth - 165,
                        Math.max(12, sx - 65)
                    );
                    const labelY = Math.min(
                        window.innerHeight - 52,
                        Math.max(12, sy - 50)
                    );
                    const label = descricao.length > 24
                        ? `${descricao.slice(0, 23)}…`
                        : descricao;

                    wrap.innerHTML = `
                      <style>
                        @keyframes demoArrowPulse {
                          from { opacity:.72; stroke-width:10; }
                          to { opacity:1; stroke-width:15; }
                        }
                        @keyframes demoTargetPulse {
                          from { r:17; opacity:.95; }
                          to { r:27; opacity:.25; }
                        }
                      </style>
                      <svg width="100%" height="100%" viewBox="0 0 ${window.innerWidth} ${window.innerHeight}">
                        <defs>
                          <marker id="demoArrowHead" markerWidth="15" markerHeight="15"
                                  refX="12" refY="6" orient="auto" markerUnits="strokeWidth">
                            <path d="M0,0 L0,12 L13,6 z"
                                  fill="#FFD400" stroke="#2B174A" stroke-width="1.4"/>
                          </marker>
                          <filter id="demoArrowShadow" x="-40%" y="-40%" width="180%" height="180%">
                            <feDropShadow dx="0" dy="4" stdDeviation="3"
                                          flood-color="#000000" flood-opacity=".75"/>
                          </filter>
                        </defs>
                        <path d="M ${sx} ${sy} Q ${cx} ${cy} ${x} ${y}"
                              fill="none" stroke="#FFD400" stroke-width="12"
                              stroke-linecap="round" marker-end="url(#demoArrowHead)"
                              filter="url(#demoArrowShadow)"
                              style="animation:demoArrowPulse .48s ease-in-out infinite alternate"/>
                        <circle cx="${x}" cy="${y}" r="17" fill="none"
                                stroke="#FFF4A3" stroke-width="5"
                                style="animation:demoTargetPulse .55s ease-out infinite"/>
                        <rect x="${labelX}" y="${labelY}" width="153" height="37" rx="10"
                              fill="#FFD400" stroke="#2B174A" stroke-width="3"
                              filter="url(#demoArrowShadow)"/>
                        <text x="${labelX + 76.5}" y="${labelY + 24}"
                              text-anchor="middle" font-family="Arial,sans-serif"
                              font-size="14" font-weight="900" fill="#2B174A">${label}</text>
                      </svg>`;
                    document.body.appendChild(wrap);
                }""",
                {"x": x, "y": y, "descricao": descricao},
            )
            print(f"    ↳ seta + clique: {descricao}")
            cliques_com_seta.append(descricao)
            _pausa(espera)
            alvo.click()
            _pausa(0.35)
            try:
                pagina.evaluate(
                    "document.getElementById('demo-click-arrow')?.remove()"
                )
            except Exception:
                pass

        def abrir(caminho: str, espera: float = 3.0, titulo: str = "") -> None:
            """Abre apenas o primeiro ecrã; o resto da demo usa cliques reais."""
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
        abrir("/", 5, "Página de apresentação pública")
        if "Boladas-ponto-com" not in pagina.locator(".hero-title").inner_text():
            raise RuntimeError("A página inicial pública não mostrou a apresentação esperada.")
        if "Do zero ao infinito." not in pagina.locator(".hero-slogan").inner_text():
            raise RuntimeError("A página inicial pública não mostrou o slogan oficial.")
        rolar(4)

        # 2. As regras do jogo — navegação feita por clique no rodapé
        apontar_e_clicar(".footer a[href='/termos']", "Termos de Uso")
        pagina.wait_for_load_state("networkidle", timeout=20000)
        pagina.wait_for_url("**/termos", timeout=20000)
        print("  → Termos de Uso")
        _pausa(4)
        rolar(2)

        if com_login:
            # 3. Entrar — todos os campos e o botão recebem a seta
            try:
                apontar_e_clicar(".topbar nav a[href='/entrar']", "Entrar")
                pagina.wait_for_load_state("networkidle", timeout=20000)
                print("  → Entrar")
                _pausa(2)
                # o campo aceita email ou telefone, conforme o formulário
                campo = "#identifier" if pagina.query_selector("#identifier") else "#email"
                apontar_e_clicar(campo, "Email ou telefone")
                pagina.fill(campo, EMAIL_DEMO)
                _pausa(0.8)
                apontar_e_clicar("#password", "Password")
                pagina.fill("#password", PASSWORD_DEMO)
                _pausa(0.8)
                # botão dentro do formulário de email/password: um seletor
                # genérico apanhava o botão de login com Google, que aparece
                # primeiro na página, e entrava com a conta errada
                apontar_e_clicar(
                    "form[action='/entrar'] button[type=submit]", "Confirmar entrada"
                )
                pagina.wait_for_load_state("networkidle", timeout=20000)
                pagina.wait_for_url("**/explorar", timeout=20000)
                if "Ana Machava" not in pagina.locator(".nav-user").inner_text():
                    raise RuntimeError("A sessão de demonstração não ficou autenticada.")
                _pausa(3)
            except Exception as exc:
                raise RuntimeError(f"Login da demonstração falhou: {exc}") from exc

            # 4. O que já existe publicado — o login já abriu o feed
            print("  → Explorar negócios")
            _pausa(5)
            rolar(4)

            # 5. Comparar produtos e preços — clique real na barra superior
            try:
                apontar_e_clicar(
                    ".topbar nav a[href='/comparar']", "Comparar Preços e GPS"
                )
                pagina.wait_for_load_state("networkidle", timeout=20000)
                print("  → Comparar preços")
                _pausa(3)
                apontar_e_clicar("input[name='q']", "Pesquisar produto")
                pagina.fill("input[name='q']", "Cimento")
                # Coordenadas de demonstração em Maputo. Evitam enviar os
                # campos numéricos vazios e permitem mostrar a distância.
                pagina.evaluate(
                    """() => {
                        document.querySelector('#latInput').value = '-25.9692';
                        document.querySelector('#lonInput').value = '32.5732';
                    }"""
                )
                _pausa(1)
                apontar_e_clicar(
                    "#compareForm button[type='submit']", "Comparar Preços"
                )
                pagina.wait_for_load_state("networkidle", timeout=20000)
                if pagina.get_by_text("Cimento Limpopo", exact=False).count() == 0:
                    raise RuntimeError("A comparação não mostrou o resultado de cimento esperado.")
                _pausa(4)
                rolar(2)
            except Exception as exc:
                raise RuntimeError(f"Comparador da demonstração falhou: {exc}") from exc

            # 6. Um anúncio concreto — regresso ao feed por clique real
            try:
                apontar_e_clicar(".topbar nav a[href='/explorar']", "Voltar ao Feed")
                pagina.wait_for_load_state("networkidle", timeout=20000)
                print("  → Voltar ao feed")
                _pausa(2)
                # Prefere um anúncio que declare proveniência, para a cena
                # seguinte poder mostrar a verificação real.
                from app import db

                seletor_post = None
                for link in pagina.locator("a[href^='/posts/']").all():
                    href = link.get_attribute("href") or ""
                    partes = href.strip("/").split("/")
                    if len(partes) == 2:
                        post = db.get_post(partes[1])
                        if (
                            post is not None
                            and post["theme"] == "Telemóvel Usado Samsung A12"
                            and post["provenance_key"]
                        ):
                            seletor_post = f"a[href='{href}']"
                            break
                if seletor_post is None:
                    raise RuntimeError(
                        "O feed não contém o anúncio Samsung A12 com proveniência."
                    )
                apontar_e_clicar(seletor_post, "Ver Anúncio")
                pagina.wait_for_load_state("networkidle", timeout=20000)
                if "Telemóvel Usado Samsung A12" not in pagina.locator("h1").inner_text():
                    raise RuntimeError("Foi aberto um anúncio diferente do Samsung A12.")
                _pausa(4)
                rolar(3)
                print("  → Post individual")

                # 7. A peça central: verificar contra o B2 ao vivo
                botao = pagina.query_selector("a[href$='/provenance']")
                if botao:
                    apontar_e_clicar(
                        "a[href$='/provenance']", "Ver Proveniência B2"
                    )
                    pagina.wait_for_load_state("networkidle", timeout=20000)
                    if "Proveniência" not in pagina.locator("h1").inner_text():
                        raise RuntimeError("A página de proveniência não foi aberta.")
                    _pausa(3)
                    print("  → Proveniência")
                    verificar = pagina.query_selector("#verify-btn")
                    if verificar:
                        apontar_e_clicar("#verify-btn", "Verificar no B2")
                        print("  → Verificação ao vivo contra o Backblaze B2")
                        _pausa(9)  # a verificação vai mesmo buscar os ficheiros
                    rolar(3)
            except Exception as exc:
                raise RuntimeError(f"Cena do anúncio/proveniência falhou: {exc}") from exc

            # 8. Criar — clique real na barra superior
            apontar_e_clicar(".topbar nav a[href='/criar']", "Anunciar")
            pagina.wait_for_load_state("networkidle", timeout=20000)
            if "Criar post" not in pagina.locator("h1").inner_text():
                raise RuntimeError("O formulário de criação não foi aberto.")
            print("  → Criar anúncio")
            _pausa(5)
            rolar(3)

            # 9. Empresas e sócios — clique real na barra superior
            apontar_e_clicar(
                ".topbar nav a[href='/empresa']", "Minhas empresas"
            )
            pagina.wait_for_load_state("networkidle", timeout=20000)
            if "As minhas empresas" not in pagina.locator("h1").inner_text():
                raise RuntimeError("A lista de empresas não foi aberta.")
            print("  → As minhas empresas")
            _pausa(4)
            rolar(2)

        print(f"  → Total de cliques com seta: {len(cliques_com_seta)}")

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
