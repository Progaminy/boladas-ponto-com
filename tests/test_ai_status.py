"""Uma etapa opcional indisponível não é uma avaria. Estes testes fixam que
a falta de IA é apresentada como espera, sem esconder o motivo real."""

import pytest

from app.ai_status import interpretar_falha_de_imagem

ERRO_QUOTA_GEMINI = (
    "Todos os provedores de imagem configurados falharam. vertex: Falha na "
    "geração de imagem via google-vertex-express (rate_limit): 429 "
    "RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded "
    "your current quota', 'status': 'RESOURCE_EXHAUSTED'}} | gmicloud: "
    "GMICloud submit failed (402): Insufficient credits."
)


def test_sem_falha_nao_produz_estado():
    assert interpretar_falha_de_imagem(None) is None
    assert interpretar_falha_de_imagem("") is None


def test_falta_de_quota_e_apresentada_como_espera():
    estado = interpretar_falha_de_imagem(ERRO_QUOTA_GEMINI)
    assert estado.e_espera
    assert estado.tipo == "aguarda"
    # a explicação tranquiliza sobre o que continua a funcionar
    assert "aguardar disponibilidade" in estado.explicacao
    assert "publicado" in estado.explicacao


def test_a_explicacao_nao_despeja_jargao_tecnico():
    """O que a pessoa lê primeiro não pode ser um bloco de JSON."""
    estado = interpretar_falha_de_imagem(ERRO_QUOTA_GEMINI)
    for jargao in ["429", "RESOURCE_EXHAUSTED", "{", "gmicloud", "402"]:
        assert jargao not in estado.explicacao


def test_o_motivo_real_continua_disponivel():
    """Não fingir: o erro do provedor fica acessível, apenas em segundo plano."""
    estado = interpretar_falha_de_imagem(ERRO_QUOTA_GEMINI)
    assert "429" in estado.detalhe_tecnico
    assert "Insufficient credits" in estado.detalhe_tecnico


@pytest.mark.parametrize(
    "erro",
    [
        "GMICloud submit failed (402): Insufficient balance",
        "429 RESOURCE_EXHAUSTED",
        "Quota exceeded for metric ... limit: 0",
        "rate limit exceeded",
    ],
)
def test_variantes_de_falta_de_saldo_sao_espera(erro):
    assert interpretar_falha_de_imagem(erro).e_espera


def test_falta_de_configuracao_nao_e_espera_mas_tambem_nao_alarma():
    estado = interpretar_falha_de_imagem(
        "Nenhum provedor de IA configurado. Define VERTEX_EXPRESS_API_KEY."
    )
    assert estado.tipo == "indisponivel"
    assert not estado.e_espera
    assert "publicado e funcional" in estado.explicacao


def test_erro_desconhecido_nao_quebra_e_mantem_o_detalhe():
    estado = interpretar_falha_de_imagem("Erro esquisito nunca visto")
    assert estado.tipo == "erro"
    assert estado.detalhe_tecnico == "Erro esquisito nunca visto"
    assert "publicado e funcional" in estado.explicacao


def test_titulo_nunca_usa_linguagem_de_avaria():
    """O anúncio funciona; o título não pode sugerir que falhou."""
    for erro in [ERRO_QUOTA_GEMINI, "402 Insufficient credits", "erro qualquer"]:
        titulo = interpretar_falha_de_imagem(erro).titulo.lower()
        for palavra in ["falha", "falhou", "erro", "problema"]:
            assert palavra not in titulo
