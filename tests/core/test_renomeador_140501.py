import pandas as pd

from core.files.renomeador import limpar_nomes_relatorios


def test_140501_preserves_cashflow_folder_and_normalizes_branch_filename(tmp_path):
    auxiliary = tmp_path / 'dRevendas.xlsx'
    pd.DataFrame([{'idRevenda': '2210003', 'nUnidade': '3'}]).to_excel(auxiliary, index=False)
    source = tmp_path / '140501'
    source.mkdir()
    (source / '14,05,01_nUnidade_2210003.csv').write_text('A;B\n1;2\n', encoding='utf-8')
    limpar_nomes_relatorios(tmp_path, auxiliary)
    assert (source / '14.05.01_3.csv').read_text(encoding='utf-8') == 'A;B\n1;2\n'
