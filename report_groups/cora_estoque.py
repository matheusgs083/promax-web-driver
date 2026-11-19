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
    # Códigos PUXADA da dRevendas (os mesmos aceitos pela API Cora).
    "units": ["487570", "820288", "747530", "747548", "1036580", "1044303", "1044591", "1045180"],
}
