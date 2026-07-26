"""Traduz falhas dos provedores de IA em estados compreensíveis.

Um `429 RESOURCE_EXHAUSTED` com um bloco JSON não diz nada a quem está a
vender sapatos. Mas escondê-lo por completo também não serve: o projeto
não finge.

O equilíbrio: em primeiro plano, uma frase honesta sobre o que está a
acontecer — normalmente uma espera, não uma avaria —, e o detalhe técnico
real guardado por baixo, para quem o quiser ver ou precisar de o depurar.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EstadoIA:
    # 'aguarda' quando é questão de disponibilidade/quota (não é avaria),
    # 'indisponivel' quando falta configuração, 'erro' para o resto.
    tipo: str
    titulo: str
    explicacao: str
    detalhe_tecnico: str

    @property
    def e_espera(self) -> bool:
        return self.tipo == "aguarda"


_SINAIS_DE_QUOTA = (
    "429",
    "resource_exhausted",
    "quota",
    "rate limit",
    "rate_limit",
    "insufficient credits",
    "insufficient balance",
    "402",
    "limit: 0",
)

_SINAIS_DE_CONFIGURACAO = (
    "não configurada",
    "nao configurada",
    "não está configurado",
    "nenhum provedor",
    "api key",
    "unauthorized",
    "401",
)


def interpretar_falha_de_imagem(erro: str | None) -> EstadoIA | None:
    """Devolve None quando não houve falha nenhuma."""
    if not erro:
        return None

    bruto = erro.strip()
    minusculas = bruto.lower()

    if any(sinal in minusculas for sinal in _SINAIS_DE_QUOTA):
        return EstadoIA(
            tipo="aguarda",
            titulo="Imagem por gerar",
            explicacao=(
                "A geração de imagem por IA está a aguardar disponibilidade. "
                "O anúncio já está publicado e completo — o texto, o preço e o "
                "contacto funcionam normalmente, e a imagem pode ser "
                "acrescentada mais tarde."
            ),
            detalhe_tecnico=bruto,
        )

    if any(sinal in minusculas for sinal in _SINAIS_DE_CONFIGURACAO):
        return EstadoIA(
            tipo="indisponivel",
            titulo="Imagem por gerar",
            explicacao=(
                "A geração de imagem por IA ainda não está ativa nesta "
                "instalação. O anúncio está publicado e funcional."
            ),
            detalhe_tecnico=bruto,
        )

    return EstadoIA(
        tipo="erro",
        titulo="Imagem por gerar",
        explicacao=(
            "Não foi possível gerar a imagem desta vez. O anúncio está "
            "publicado e funcional; podes tentar gerar a imagem mais tarde."
        ),
        detalhe_tecnico=bruto,
    )
