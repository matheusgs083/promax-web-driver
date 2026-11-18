from __future__ import annotations


class PromaxHttpErro(RuntimeError):
    """Falha generica do cliente HTTP do Promax."""


class LoginRecusado(PromaxHttpErro):
    pass


class SemPermissao(PromaxHttpErro):
    pass


class RelatorioSemConteudo(PromaxHttpErro):
    pass


class ExportacaoNaoEntendida(PromaxHttpErro):
    """O Promax respondeu algo que o cliente ainda nao sabe interpretar.

    O rastro gravado mostra a resposta para ajustarmos o fluxo.
    """


class PromaxInacessivel(PromaxHttpErro):
    """Rede ou servidor do Promax nao respondeu."""


class ArquivoBloqueado(PromaxHttpErro):
    """O relatorio veio, mas o arquivo de destino esta aberto em outro programa
    (ex.: Excel) e o Windows nao deixa substituir."""
