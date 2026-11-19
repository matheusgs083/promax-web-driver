REPORT_GROUP = {
    "key": "cora_estoque",
    "name": "Cora - Grade de Estoque",
    "description": "Baixa a grade de estoque do portal Cora, uma unidade de entrega por vez.",
    "routines": [
        {
            "id": "grade_estoque",
            "name": "Grade de Estoque Cora",
            "output_folders": ["cora_estoque"],
        },
    ],
    # Sem "units": a tela envia os códigos Promax de sempre e o worker traduz
    # para o código Cora (_CORA_ESTOQUE_UNIT_BY_PROMAX_UNIT em promax_runner.py).
    # Listar aqui os códigos Cora faz a API recusar os códigos Promax (422).
}
