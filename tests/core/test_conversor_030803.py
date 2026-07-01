from pathlib import Path

import pytest

from core.files import conversor_030803


def test_parse_load_line_with_origin_and_current_location():
    row, current_date = conversor_030803._parse_load_line(
        "13/11/2014 1214 0 Spot 0 Nao Cadastrado Ext Ext PW00342S Fechado Nao",
        None,
    )

    assert current_date == "13/11/2014"
    assert row == {
        "Liberacao": "13/11/2014",
        "Carga": "1214",
        "Mapa": "0",
        "Veiculo": "Spot",
        "Frota": "0",
        "Cod_Spot": "Nao",
        "Motorista": "Cadastrado",
        "Origem": "Ext",
        "Atual": "Ext",
        "Usuario": "PW00342S",
        "Situacao": "Fechado",
        "Apurado": "Nao",
    }


def test_parse_load_line_reuses_previous_date_when_line_has_no_date():
    row, current_date = conversor_030803._parse_load_line(
        "12815 0 Spot 0 Nao Cadastrado PW00342S Fechado Nao",
        "11/05/2016",
    )

    assert current_date == "11/05/2016"
    assert row["Liberacao"] == "11/05/2016"
    assert row["Carga"] == "12815"
    assert row["Origem"] == ""
    assert row["Atual"] == ""
    assert row["Usuario"] == "PW00342S"


def test_converter_writes_same_name_xlsx_and_deletes_pdf(monkeypatch, tmp_path):
    pdf_path = tmp_path / "030803_3.PDF"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(
        conversor_030803,
        "extrair_linhas_030803",
        lambda _: [
            {
                "Liberacao": "04/05/2026",
                "Carga": "90762",
                "Mapa": "72",
                "Veiculo": "RLR8D79",
                "Frota": "Padronizado",
                "Cod_Spot": "7373",
                "Motorista": "FABIANO DE CARVALHO",
                "Origem": "Rot",
                "Atual": "Rot",
                "Usuario": "PW00342S",
                "Situacao": "Fechado",
                "Apurado": "Nao",
            }
        ],
    )

    xlsx_path = conversor_030803.converter_030803_pdf_para_xlsx(pdf_path)

    assert xlsx_path == Path(tmp_path / "030803_3.xlsx")
    assert xlsx_path.exists()
    assert not pdf_path.exists()


def test_converter_can_keep_pdf_when_requested(monkeypatch, tmp_path):
    pdf_path = tmp_path / "030803_3.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(conversor_030803, "extrair_linhas_030803", lambda _: [{"Carga": "1"}])
    monkeypatch.setattr(conversor_030803, "salvar_030803_xlsx", lambda rows, path: path.write_bytes(b"xlsx"))

    xlsx_path = conversor_030803.converter_030803_pdf_para_xlsx(pdf_path, apagar_pdf=False)

    assert xlsx_path == tmp_path / "030803_3.xlsx"
    assert xlsx_path.read_bytes() == b"xlsx"
    assert pdf_path.exists()


def test_converter_keeps_pdf_when_xlsx_generation_fails(monkeypatch, tmp_path):
    pdf_path = tmp_path / "030803_3.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(conversor_030803, "extrair_linhas_030803", lambda _: [{"Carga": "1"}])

    def fail_to_save(_rows, _path):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(conversor_030803, "salvar_030803_xlsx", fail_to_save)

    with pytest.raises(RuntimeError, match="falha simulada"):
        conversor_030803.converter_030803_pdf_para_xlsx(pdf_path)

    assert pdf_path.exists()
    assert not list(tmp_path.glob("*.tmp.xlsx"))


def test_multi_converter_processes_all_pdfs_from_directory(monkeypatch, tmp_path):
    first_pdf = tmp_path / "030803_1.pdf"
    second_pdf = tmp_path / "030803_2.PDF"
    ignored = tmp_path / "030803_3.txt"
    first_pdf.write_bytes(b"%PDF-1.4 fake")
    second_pdf.write_bytes(b"%PDF-1.4 fake")
    ignored.write_text("nao e pdf", encoding="utf-8")

    monkeypatch.setattr(conversor_030803, "extrair_linhas_030803", lambda _: [{"Carga": "1"}])
    monkeypatch.setattr(conversor_030803, "salvar_030803_xlsx", lambda rows, path: path.write_bytes(b"xlsx"))

    arquivos = conversor_030803.converter_multiplos_030803_pdf_para_xlsx([tmp_path])

    assert arquivos == [tmp_path / "030803_1.xlsx", tmp_path / "030803_2.xlsx"]
    assert not first_pdf.exists()
    assert not second_pdf.exists()
    assert ignored.exists()
