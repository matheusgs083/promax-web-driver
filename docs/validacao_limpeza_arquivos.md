# Validacao de organizacao de arquivos do promax-web-driver

## Estado atual

O repositorio tem duas fontes diferentes de bagunca:

1. Artefatos locais gerados por execucao, debug e testes.
2. Arquivos versionados na raiz que parecem sobras de desenvolvimento ou wrappers antigos.

Nada foi apagado nesta validacao.

## Alteracoes pendentes ja existentes

O `git status` mostra alteracoes ainda nao commitadas da rotina `150501` nao versionada:

- `cli.py`
- `tests/test_cli_profiles.py`
- `entrypoints/reports/relatorio_150501_nao_versionado.py`
- `main150501NaoVersionado.py`
- `tests/test_relatorio_150501_nao_versionado.py`

Esses arquivos nao devem ser tratados como sujeira. Eles fazem parte da mudanca recente da `150501`.

## Sujeira local ignorada pelo git

Esses itens ocupam espaco e confundem a pasta, mas nao aparecem no `git status` porque ja estao ignorados ou deveriam ser tratados como artefato local.

| Caminho | Arquivos | Tamanho aproximado | Acao sugerida |
| --- | ---: | ---: | --- |
| `logs/` | 609 | 108,77 MB | Limpar historico antigo, principalmente `logs/mitm`, `logs/visual_debug` e logs de relatorios antigos. |
| `venv/` | 11383 | 357,43 MB | Manter localmente, nunca versionar. |
| `__pycache__/` | 28 | 0,09 MB | Pode apagar sem risco. |
| `.pytest_cache/` | 5 | 0,04 MB | Pode apagar sem risco. |
| `.pytest_tmp/` | 1 | 0,01 MB | Pode apagar sem risco. |
| `maps/` | 17 | 0,14 MB | Conteudo local de mapeamento; manter ignorado, revisar apenas se algum mapa precisa virar documentacao. |

## Arquivos versionados com maior chance de limpeza

| Arquivo | Motivo | Acao sugerida |
| --- | --- | --- |
| `mitm_mcp_traffic.db` | Banco SQLite de trafego/debug rastreado no git. Nao deveria fazer parte do codigo. | Remover do versionamento e adicionar regra no `.gitignore` para `mitm*.db` ou `*.db`, se nao houver fixture real de banco. |
| `testar_030206_pdf_intervalo.py` | Script manual de debug sem referencia interna. | Mover para `tools/manual_tests/` ou remover se nao for mais usado. |
| `testar_030302_mapa.py` | Script manual de debug sem referencia interna. | Mover para `tools/manual_tests/` ou remover se nao for mais usado. |
| `testar_carga_concorrente_3.py` | Script de bancada de concorrencia. | Mover para `tools/manual_tests/` ou remover. |
| `testar_carga_concorrente_8.py` | Script de bancada de concorrencia. | Mover para `tools/manual_tests/` ou remover. |
| `testar_download_http_020220.py` | Script manual de download. | Mover para `tools/manual_tests/` ou remover. |
| `testar_estabilidade_120616_http.py` | Script manual de estabilidade. | Mover para `tools/manual_tests/` ou remover. |
| `testar_geracao_concorrente.py` | Script de bancada ainda aparece com poucas referencias, mas nao e teste automatizado. | Mover para `tools/manual_tests/` e documentar como uso manual. |
| `testar_sessoes_multirrotina.py` | Script de bancada para sessoes. | Mover para `tools/manual_tests/` ou remover. |

## Arquivos que pareciam bagunca, mas foram tratados com cuidado

Os `main*.py` da raiz eram quase todos wrappers finos para manter compatibilidade com chamadas antigas, atalhos, agendamentos ou execucoes manuais. Mesmo quando o `rg` nao encontrava referencia interna, eles podiam ser chamados de fora do repositorio.

Pela regra operacional atual informada em 10/09/2026, os relatorios sao executados pelo orquestrador/`cli.py`. O worker do `bot_api` tambem chama `cli.py`, nao os wrappers de relatorio da raiz.

Com isso, os wrappers e scripts abaixo foram movidos para `old/`:

- `main.py`
- `main030302.py`
- `main030303.py`
- `main03030702.py`
- `main030312.py`
- `main030330.py`
- `main140510.py`
- `main150501NaoVersionado.py`
- `mainRelatorios.py`
- `mainRelatoriosFechamento.py`
- `mainAdf.py`
- `mainBotZap.py`
- `mainEstoque.py`
- `mainExtrairLogs.py`
- `mainFechamentoMapa.py`
- `mainFluxoCaixa.py`
- `mainGiro.py`
- `mainInadimplencia.py`
- `mainObz.py`
- `mainOutros.py`
- `mainPedidos.py`
- `mainReprocessarPublicacao.py`
- `alterarCEMC.py`

Permaneceram na raiz apenas:

- `cli.py`, entrada oficial do orquestrador;
- `mainWorker.py`, entrada direta do worker local;
- `mainMapeador.py`, ferramenta direta do mapeador.

## Conversores soltos movidos

| Arquivo | Situacao | Acao sugerida |
| --- | --- | --- |
| `030803tocsv.py` | Wrapper de conversao do relatorio 03.08.03. | Movido para `old/`. |
| `prestacao_contas_tocsv.py` | Wrapper de conversao de prestacao de contas. | Movido para `old/`. |
| `generate_csv.py` | Arquivo grande e sem referencia interna clara. | Movido para `old/`. |

## Ajustes de `.gitignore` recomendados

O `.gitignore` ja ignora logs, CSV, XLSX, caches, `venv` e `maps`, mas esta duplicado e pode ser limpo.

Regras recomendadas para adicionar ou reforcar:

```gitignore
mitm*.db
*.sqlite
worker-*.log
logs/mitm/
logs/visual_debug/
```

Tambem vale consolidar as regras duplicadas de Python, IDE, logs e temp.

## Plano de limpeza seguro aplicado

1. As alteracoes reais da `150501` nao versionada permaneceram em arquivos proprios de entrypoint, CLI e testes.
2. `mitm_mcp_traffic.db` saiu da raiz e foi movido para `old/`.
3. Wrappers de relatorio e de processos manuais sairam da raiz, pois o uso atual e pelo orquestrador/`cli.py`.
4. `testar_*.py` foi movido para `old/`.
5. Conversores soltos foram movidos para `old/`.
6. Caches e logs ignorados continuam fora do caminho versionado.
7. `mainWorker.py` e `mainMapeador.py` foram preservados na raiz por serem os unicos usos diretos atuais informados.

## Limpeza aplicada

Em 10/09/2026, os wrappers e scripts soltos da raiz foram movidos para `old/`.

Permaneceram na raiz:

- `cli.py`, entrada oficial usada pelo worker/orquestrador.
- `mainWorker.py`, usado para iniciar o worker local.
- `mainMapeador.py`, usado diretamente para o mapeador.
- arquivos de configuracao/documentacao do projeto.

Tambem foram movidos para `old/` o banco `mitm_mcp_traffic.db` e os logs vazios `worker-fechamento.*.log`.

## Conclusao

A maior bagunca real nao esta nos Page Objects nem nos entrypoints principais. Esta na raiz do projeto e nos artefatos de debug. A limpeza mais segura e:

- manter a raiz limitada a `cli.py`, `mainWorker.py`, `mainMapeador.py` e arquivos de configuracao/documentacao;
- usar `old/` como referencia historica temporaria para wrappers, scripts manuais e artefatos antigos;
- manter novos fluxos pelo orquestrador/`cli.py`, sem reintroduzir wrappers soltos na raiz.
