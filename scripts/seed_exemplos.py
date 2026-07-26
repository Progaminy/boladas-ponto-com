#!/usr/bin/env python3
"""Cria contas de exemplo para demonstração e para os jurados explorarem.

Cobre os casos de uso reais da plataforma:

  - vendedores particulares, sem empresa (mercado informal, venda ocasional);
  - empresas de categorias diferentes (farmácia, ferragens, padaria);
  - uma empresa com dois sócios, cada um com o seu próprio acesso;
  - um utilizador que gere mais do que uma empresa.

Com `--posts`, cria também anúncios reais: a legenda, a chamada para ação e
as hashtags são geradas pela IA de verdade e enviadas para o Backblaze B2,
com manifesto de proveniência. Sem créditos de imagem, os posts ficam sem
imagem gerada — e dizem-no, em vez de mostrarem uma imagem de mentira.

Uso:
    python3 scripts/seed_exemplos.py            # só contas e empresas
    python3 scripts/seed_exemplos.py --posts    # + anúncios reais (usa a IA)
    python3 scripts/seed_exemplos.py --limpar   # apaga os exemplos e recria
"""

import argparse
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import auth, db  # noqa: E402
from app.models import BusinessInput  # noqa: E402

PASSWORD_EXEMPLO = "boladas2026"

# O plano gratuito do Gemini permite 20 gerações por dia e por modelo
# (GenerateRequestsPerDayPerProjectPerModel-FreeTier). Cada anúncio gasta uma.
# A pausa evita o limite por minuto; a quota diária não se contorna com espera.
PAUSA_ENTRE_ANUNCIOS_S = 8

# Todas as contas de exemplo partilham este sufixo, para poderem ser
# identificadas e removidas sem tocar em contas reais.
SUFIXO = "@exemplo.boladas.mz"

UTILIZADORES = [
    # (email_local, nome, descrição do caso)
    ("carlota", "Carlota Nhamirre", "vende roupa em segunda mão, sem empresa"),
    ("jaime", "Jaime Sitoe", "vende telemóveis usados no mercado informal"),
    ("ana", "Ana Machava", "farmacêutica, proprietária da farmácia"),
    ("rui", "Rui Bila", "sócio da mesma farmácia"),
    ("salomao", "Salomão Cuna", "dono de ferragens e de uma padaria"),
]

EMPRESAS = [
    {
        "chave": "farmacia",
        "dono": "ana",
        "socios": ["rui"],
        "dados": BusinessInput(
            name="Farmácia Vida Nova",
            category="farmacia_saude",
            description="Medicamentos, primeiros socorros e produtos de higiene.",
            location="Maputo, Alto-Maé",
            contact="+258 84 100 0001",
        ),
    },
    {
        "chave": "ferragens",
        "dono": "salomao",
        "socios": [],
        "dados": BusinessInput(
            name="Ferragens Cuna & Filhos",
            category="ferragens_construcao",
            description="Cimento, tintas, ferramentas e material eléctrico.",
            location="Matola, Machava",
            contact="+258 84 100 0002",
        ),
    },
    {
        "chave": "padaria",
        "dono": "salomao",
        "socios": [],
        "dados": BusinessInput(
            name="Padaria Pão Quente",
            category="padaria_pastelaria",
            description="Pão fresco todas as manhãs, bolos por encomenda.",
            location="Matola, Fomento",
            contact="+258 84 100 0003",
        ),
    },
    {
        "chave": "mercado",
        "dono": "jaime",
        "socios": [],
        "dados": BusinessInput(
            name="Banca do Jaime",
            category="Mercado Informal",  # categoria fora da lista, escrita à mão
            description="Telemóveis usados, capas e carregadores.",
            location="Maputo, Mercado Xipamanine",
            contact="+258 84 100 0004",
        ),
    },
]


ANUNCIOS = [
    {
        "autor": "carlota",
        "empresa": None,
        "business": "Camisa de algodão azul, tamanho M",
        "category": "moda_vestuario",
        "price_mt": 450,
        "location": "Maputo, Polana",
        "contact": "+258 84 200 0001",
        "description": "Camisa de algodão azul, tamanho M, usada duas vezes, sem defeitos.",
        "description_source": "manual",
    },
    {
        "autor": "jaime",
        "empresa": "mercado",
        "business": "Telemóvel usado, bateria nova",
        "category": "Mercado Informal",
        "price_mt": 3500,
        "location": "Maputo, Mercado Xipamanine",
        "contact": "+258 84 100 0004",
        "description": "Telemóvel em segunda mão, com bateria substituída recentemente.",
        "description_source": "manual",
    },
    {
        "autor": "ana",
        "empresa": "farmacia",
        "business": "Medição de tensão arterial gratuita",
        "category": "farmacia_saude",
        "price_mt": None,
        "location": "Maputo, Alto-Maé",
        "contact": "+258 84 100 0001",
        "description": "Serviço de medição de tensão arterial, sem custo, durante o horário da farmácia.",
        "description_source": "manual",
    },
    {
        "autor": "salomao",
        "empresa": "ferragens",
        "business": "Saco de cimento 50 kg",
        "category": "ferragens_construcao",
        "price_mt": 620,
        "location": "Matola, Machava",
        "contact": "+258 84 100 0002",
        "description": "Cimento em saco de 50 kg, disponível em quantidade para obra.",
        "description_source": "manual",
    },
    {
        "autor": "salomao",
        "empresa": "padaria",
        "business": "Bolo de aniversário por encomenda",
        "category": "padaria_pastelaria",
        "price_mt": 850,
        "location": "Matola, Fomento",
        "contact": "+258 84 100 0003",
        "description": "Bolos por encomenda para aniversários, feitos no próprio dia.",
        "description_source": "manual",
    },
]


def _email(local: str) -> str:
    return f"{local}{SUFIXO}"


def limpar() -> None:
    with db.get_conn() as conn:
        ids = [
            r["user_id"]
            for r in conn.execute(
                "SELECT user_id FROM users WHERE email LIKE ?", (f"%{SUFIXO}",)
            )
        ]
        if not ids:
            print("Nada para limpar.")
            return
        marcas = ",".join("?" * len(ids))
        conn.execute(f"DELETE FROM posts WHERE user_id IN ({marcas})", ids)
        conn.execute(
            f"DELETE FROM business_members WHERE user_id IN ({marcas})", ids
        )
        conn.execute(f"DELETE FROM businesses WHERE user_id IN ({marcas})", ids)
        conn.execute(f"DELETE FROM users WHERE user_id IN ({marcas})", ids)
    print(f"Removidas {len(ids)} contas de exemplo.")


def criar_anuncios(ids: dict[str, str], empresas: dict[str, str]) -> None:
    """Cria anúncios reais: a legenda é mesmo gerada pela IA e os ficheiros
    vão mesmo para o B2. Só corre com --posts, para não gastar chamadas à IA
    sem intenção."""
    from app.models import PostInput, PublisherType
    from app.routers.posts import _run_generation

    print("\nAnúncios (geração real — pode demorar):")
    for indice, anuncio in enumerate(ANUNCIOS):
        # o plano gratuito do Gemini limita pedidos por minuto; sem esta pausa
        # os últimos anúncios falhavam com 429 mesmo estando tudo correto
        if indice:
            time.sleep(PAUSA_ENTRE_ANUNCIOS_S)
        autor_id = ids[anuncio["autor"]]
        business_id = empresas.get(anuncio["empresa"]) if anuncio["empresa"] else None
        # publicar em nome de uma empresa exige a marca; sem empresa fica None
        empresa = db.get_business(business_id) if business_id else None
        brand_name = empresa["name"] if empresa else None

        # só conta como existente se ficou mesmo publicado: um anúncio que
        # falhou (por quota, por exemplo) tem de poder ser tentado de novo
        ja_existe = any(
            p["business"] == anuncio["business"] and p["status"] == "completed"
            for p in db.list_posts_by_user(autor_id)
        )
        if ja_existe:
            print(f"  = {anuncio['business']} (já existia)")
            continue

        entrada = PostInput(
            theme=anuncio["business"],
            business=anuncio["business"],
            category=anuncio["category"],
            publisher_type=(
                PublisherType.BUSINESS if business_id else PublisherType.INDIVIDUAL
            ),
            brand_name=brand_name,
            target_audience="Clientes em Maputo e Matola",
            objective="Vender",
            tone="amigável",
            language="pt",
            call_to_action="Contacta-me já!",
            price_mt=anuncio["price_mt"],
            location=anuncio["location"],
            contact=anuncio["contact"],
            description=anuncio["description"],
            description_source=anuncio["description_source"],
        )

        post_id = uuid.uuid4().hex
        db.create_post(post_id, autor_id, business_id, entrada)
        resultado = _run_generation(post_id, entrada)

        if resultado["status"] == "completed":
            sem_imagem = " (sem imagem gerada)" if resultado.get("image_skipped_reason") else ""
            print(f"  + {anuncio['business']}{sem_imagem}")
            continue

        erro = resultado.get("error", "")
        print(f"  ! {anuncio['business']} — falhou")
        if "PerDayPerProjectPerModel-FreeTier" in erro:
            # Esperar não resolve: a quota só volta a zero no dia seguinte.
            print(
                "\n  Quota diária do plano gratuito esgotada (20 gerações por dia).\n"
                "  Os anúncios em falta podem ser criados amanhã, correndo este\n"
                "  script outra vez — o que já existe não é duplicado."
            )
            return
        print(f"    {erro[:160]}")


def semear(com_posts: bool = False) -> None:
    db.init_db()
    hash_password = auth.hash_password(PASSWORD_EXEMPLO)
    ids: dict[str, str] = {}

    print("Contas:")
    for local, nome, descricao in UTILIZADORES:
        email = _email(local)
        existente = db.get_user_by_email(email)
        if existente:
            ids[local] = existente["user_id"]
            print(f"  = {email} (já existia)")
            continue
        user_id = uuid.uuid4().hex
        db.create_user(user_id, email, hash_password, nome)
        ids[local] = user_id
        print(f"  + {email} — {descricao}")

    print("\nEmpresas:")
    empresas_criadas: dict[str, str] = {}
    for empresa in EMPRESAS:
        dono_id = ids[empresa["dono"]]
        ja_existe = next(
            (
                b
                for b in db.list_businesses_by_user(dono_id)
                if b["name"] == empresa["dados"].name
            ),
            None,
        )
        if ja_existe:
            business_id = ja_existe["business_id"]
            print(f"  = {empresa['dados'].name} (já existia)")
        else:
            business_id = uuid.uuid4().hex
            db.create_business(business_id, dono_id, empresa["dados"])
            print(f"  + {empresa['dados'].name} — {empresa['dados'].category}")

        empresas_criadas[empresa["chave"]] = business_id
        for socio in empresa["socios"]:
            db.add_business_member(business_id, ids[socio], dono_id)
            print(f"      sócio: {_email(socio)}")

    if com_posts:
        criar_anuncios(ids, empresas_criadas)

    print(f"\nPassword de todas as contas de exemplo: {PASSWORD_EXEMPLO}")
    if not com_posts:
        print("Sem anúncios. Usa --posts para criar anúncios reais (usa a IA e o B2).")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limpar", action="store_true", help="apaga as contas de exemplo antes de criar"
    )
    parser.add_argument(
        "--posts",
        action="store_true",
        help="cria também anúncios reais (gera texto com IA e envia para o B2)",
    )
    args = parser.parse_args()

    if args.limpar:
        db.init_db()
        limpar()
    semear(com_posts=args.posts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
