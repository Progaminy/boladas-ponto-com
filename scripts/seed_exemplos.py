#!/usr/bin/env python3
"""Cria contas de exemplo para demonstração e para os jurados explorarem.

Cobre os casos de uso reais da plataforma:

  - vendedores particulares, sem empresa (mercado informal, venda ocasional);
  - empresas de categorias diferentes (farmácia, ferragens, padaria);
  - uma empresa com dois sócios, cada um com o seu próprio acesso;
  - um utilizador que gere mais do que uma empresa.

Não cria posts. Um post exige geração de imagem, que depende de créditos que
a conta não tem — inventar posts "concluídos" com imagens falsas contradiria
o princípio "Nunca fingir" que o resto do projeto segue.

Uso:
    python3 scripts/seed_exemplos.py            # cria o que faltar
    python3 scripts/seed_exemplos.py --limpar   # apaga os exemplos e recria
"""

import argparse
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import auth, db  # noqa: E402
from app.models import BusinessInput  # noqa: E402

PASSWORD_EXEMPLO = "boladas2026"

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
        conn.execute(
            f"DELETE FROM business_members WHERE user_id IN ({marcas})", ids
        )
        conn.execute(f"DELETE FROM businesses WHERE user_id IN ({marcas})", ids)
        conn.execute(f"DELETE FROM users WHERE user_id IN ({marcas})", ids)
    print(f"Removidas {len(ids)} contas de exemplo.")


def semear() -> None:
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

        for socio in empresa["socios"]:
            db.add_business_member(business_id, ids[socio], dono_id)
            print(f"      sócio: {_email(socio)}")

    print(f"\nPassword de todas as contas de exemplo: {PASSWORD_EXEMPLO}")
    print("Nenhum post foi criado: exigiria geração de imagem real (ver README).")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limpar", action="store_true", help="apaga as contas de exemplo antes de criar"
    )
    args = parser.parse_args()

    if args.limpar:
        db.init_db()
        limpar()
    semear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
