# Sistema de Automacao Promax

Projeto de RPA em Python para o sistema legado Promax, com Selenium WebDriver, Edge em IE Mode, Page Object Model e servicos auxiliares para download, publicacao e rastreio de execucao.

## Estrutura

- `entrypoints/`
  - Implementacao real dos fluxos executaveis, organizada por dominio.
  - Subpastas principais: `reports/`, `processes/`, `maintenance/` e `tools/`.
  - `main*.py` e `alterarCEMC.py` na raiz ficaram como wrappers de compatibilidade.
- `core/`
  - Infraestrutura compartilhada: driver, configuracao, logs, resultados de execucao, download, publicacao, paths e orquestracao.
- `pages/`
  - Page Objects e rotinas especificas do Promax.
- `tests/`
  - Testes unitarios e contratos basicos de regressao, agrupados em `core/`, `pages/` e `support/`.
- `docs/`
  - Contexto do projeto, code review e historico de melhorias.
- `agents/`
  - Prompts e instrucoes para agentes especializados.

## Fluxos principais

- `entrypoints/reports/relatorios.py`
  - Fluxo principal de relatorios.
- `entrypoints/reports/relatorios_fechamento.py`
  - Fluxo de fechamento.
- `entrypoints/reports/repescagem_relatorios.py`
  - Repescagem manual de relatorios.
- `entrypoints/maintenance/reprocessar_publicacao.py`
  - Reprocessamento de `logs/publicacao_pendente`.
- `entrypoints/processes/pedidos.py`
  - Digitacao de pedidos.
- `entrypoints/processes/lote_condicao.py`
  - Alteracao em lote de condicao/CEMC.

## Como executar

Fluxo recomendado:

```bash
python cli.py relatorios
python cli.py fechamento
python cli.py repescagem
python cli.py reprocessar-publicacao
python cli.py pedidos
python cli.py lote-condicao
```

Compatibilidade mantida:

```bash
python mainRelatorios.py
python mainRelatoriosFechamento.py
python main.py
python mainPedidos.py
python alterarCEMC.py
```

## Configuracao

O projeto le configuracoes via `.env` usando `core/config/settings.py`.

Pontos importantes:

- `DOWNLOAD_DIR` e a pasta intermediaria de captura.
- A publicacao final ocorre fora dela, conforme o `PublicationPlan` de cada entrypoint.
- O ambiente esperado e Windows com Edge/IE Mode, compartilhamentos de rede e desktop interativo para os fluxos de download visual.

## Documentacao util

- `docs/PROJECT_CONTEXT.md`
- `docs/code_review_tecnico.md`
- `docs/ATUALIZACOES_2026-03-23.md`
- `entrypoints/README.md`
- `tests/README.md`

## Observacao operacional

A automacao ainda precisa conviver com limitacoes do Promax legado: frames, alertas assincronos, eventos de onchange/onblur, cliques bloqueados e dependencias de UI nativa em parte do fluxo de download.



