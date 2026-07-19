# Grupos de relatorios

Esta pasta define quais grupos e rotinas aparecem no painel Promax do
`bot_api`. Cada arquivo `.py` representa um grupo, mas um grupo pode conter
varias rotinas.

Os grupos atuais sao:

```text
adf.py
bot_zap.py
estoque.py
fluxo_caixa.py
giro.py
inadimplencia.py
obz.py
outros.py
```

O worker le todos os arquivos automaticamente e envia o catalogo ao painel.
Nao e necessario cadastrar o grupo no banco.

## Estrutura do manifesto

O arquivo deve conter somente a atribuicao literal `REPORT_GROUP`:

```python
REPORT_GROUP = {
    "key": "adf",
    "name": "ADF",
    "description": "Relatorios de dados para o ADF.",
    "routines": [
        {
            "id": "030237",
            "name": "Rotina 030237",
            "output_folders": ["030237"],
        },
    ],
}
```

Campos:

- `key`: identificador do grupo e nome do arquivo sem `.py`;
- `name`: nome mostrado no painel;
- `description`: explicacao curta do grupo;
- `routines`: relatorios que podem ser selecionados nesse grupo;
- `id`: identificador interno da rotina executora;
- `name` da rotina: texto mostrado no painel;
- `output_folders`: pastas relativas onde a rotina gera os arquivos.

O arquivo `adf.py` ter uma rotina nao limita os demais grupos. Para consultar o
catalogo completo:

```powershell
cd C:\Users\SEU_USUARIO\Documents\promax-web-driver
.\venv\Scripts\python.exe -c "from core.config.report_group_loader import load_report_groups; g=load_report_groups(); [print(k, x.routine_ids) for k, x in g.items()]"
```

## Adicionar uma rotina existente a um grupo

Se a rotina ja esta implementada em
`entrypoints/reports/relatorios.py`, basta adiciona-la ao manifesto do grupo.

Exemplo:

```python
REPORT_GROUP = {
    "key": "obz",
    "name": "OBZ",
    "description": "Relatorios de acompanhamento do OBZ.",
    "routines": [
        {
            "id": "0512",
            "name": "Rotina 0512",
            "output_folders": ["0512"],
        },
        {
            "id": "150501",
            "name": "Rotina 150501",
            "output_folders": ["150501"],
        },
    ],
}
```

Depois de salvar:

1. aguarde o worker ficar ocioso;
2. abra o painel Promax;
3. clique em **Atualizar**;
4. selecione o grupo e confira as rotinas.

O worker publica o catalogo em cada heartbeat ocioso. Se existir um job em
execucao, a alteracao aparece depois que ele terminar.

## Criar um grupo novo

Crie, por exemplo, `report_groups/faturamento.py`:

```python
REPORT_GROUP = {
    "key": "faturamento",
    "name": "Faturamento",
    "description": "Relatorios usados no acompanhamento do faturamento.",
    "routines": [
        {
            "id": "030999",
            "name": "Rotina 030999",
            "output_folders": ["030999"],
        },
    ],
}
```

O nome do arquivo e o campo `key` devem ser iguais:

```text
faturamento.py -> "key": "faturamento"
```

## Criar um relatorio realmente novo

O manifesto controla o catalogo, mas nao implementa a automacao. Para um ID que
ainda nao existe, tambem e necessario:

1. criar ou reutilizar a Page Object que gera o relatorio;
2. criar a funcao `tarefa_<id>` em `entrypoints/reports/relatorios.py`;
3. registrar a funcao no dicionario `routine_runners`;
4. configurar a pasta de download;
5. configurar o destino em `publication_mapping`, quando houver publicacao;
6. adicionar a rotina ao manifesto do grupo.

Exemplo do registro da funcao:

```python
routine_runners = {
    # outras rotinas
    "030999": tarefa_030999,
}
```

Se apenas o manifesto for criado sem esse registro, o grupo aparecera no
painel, mas a execucao sera recusada com:

```text
Rotinas sem implementacao no entrypoint: 030999
```

## Validar antes de publicar

Valide todos os manifestos:

```powershell
cd C:\Users\SEU_USUARIO\Documents\promax-web-driver
.\venv\Scripts\python.exe -m pytest tests\core\test_report_group_loader.py tests\test_report_group_entrypoint.py
```

Valide um grupo pelo CLI sem depender do painel:

```powershell
.\venv\Scripts\python.exe cli.py relatorios --perfil obz --rotinas 0512 --somente-baixar
```

Use datas e unidades adicionais quando a rotina exigir.

## Regras

- mantenha um arquivo por grupo;
- coloque varias rotinas na lista `routines`;
- nao use imports, funcoes ou codigo executavel no manifesto;
- nao repita IDs de rotina dentro do mesmo grupo;
- nao repita pastas em `output_folders` dentro do mesmo grupo;
- use somente caminhos relativos;
- nao coloque senhas ou tokens nesta pasta;
- nao crie um segundo grupo com a mesma `key`.
