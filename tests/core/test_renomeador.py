from __future__ import annotations

import pandas as pd

from core.files.renomeador import limpar_nomes_relatorios


def test_renomeador_processa_raiz_e_nao_cria_subpasta_em_fluxo_caixa(tmp_path):
    auxiliar = tmp_path / "dRevendas.xlsx"
    pd.DataFrame(
        [
            {
                "idRevenda": "3610008",
                "nUnidade": "8",
                "nomeUnidade150501": "Caculé",
                "nomeUnidade120606": "CACULÉ",
            }
        ]
    ).to_excel(auxiliar, index=False)

    (tmp_path / "12,06,06_nUnidade_3610008.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    fluxo_caixa = tmp_path / "150501 fluxo de caixa"
    fluxo_caixa.mkdir()
    (fluxo_caixa / "2026-07 nomeUnidade150501_3610008.csv").write_text(
        "a,b\n1,2\n",
        encoding="utf-8",
    )

    limpar_nomes_relatorios(tmp_path, auxiliar)

    assert (tmp_path / "120606" / "12.06.06_8.csv").is_file()
    assert (fluxo_caixa / "2026-07 Caculé.csv").is_file()
    assert not (fluxo_caixa / "150501").exists()
