from pages.reports.relatorio_030805_page import _alerta_sem_movimento


def test_alerta_sem_movimento_e_ignorado():
    assert _alerta_sem_movimento("Não há movimento para listar wor")


def test_outro_alerta_nao_e_classificado_como_sem_movimento():
    assert not _alerta_sem_movimento("Data inicial inválida")
