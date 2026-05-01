from core.tools import validador_visual


def test_gerar_confidences_normaliza_e_remove_duplicados():
    assert validador_visual._gerar_confidences(0.8) == [0.8, 0.75, 0.7]


def test_gerar_confidences_respeita_limite_minimo():
    assert validador_visual._gerar_confidences(0.62) == [0.62, 0.6]
