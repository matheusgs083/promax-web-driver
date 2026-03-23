# Contexto do Projeto: promax-web-driver

## Objetivo

Automatizar rotinas do sistema legado Promax em ambiente Windows usando Python, Selenium WebDriver e Edge em IE Mode. O foco do projeto e operacional: gerar relatorios, digitar pedidos, alterar condicoes em lote e manter publicacao de artefatos para consumo interno.

## Estrutura atual

- `entrypoints/`
  - Implementacao real dos fluxos executaveis.
  - Subpastas principais: `reports/`, `processes/`, `maintenance/` e `tools/`.
- `core/`
  - Infraestrutura compartilhada.
  - Subpastas principais:
    - `browser/`
    - `config/`
    - `execution/`
    - `files/`
    - `observability/`
    - `services/`
    - `tools/`
- `pages/`
  - Page Object Model.
  - `pages/common/base_page.py`, `pages/auth/login_page.py`, `pages/common/menu_page.py`, `pages/common/rotina_page.py`, `pages/reports/*.py` e `pages/processes/*.py`.
- `tests/`
  - Cobertura unitaria para contratos de sessao, menu, movimentacao, orquestracao e reprocessamento.
  - Estruturado em `tests/core/`, `tests/pages/` e `tests/support/`.
- `docs/`
  - Contexto, revisao tecnica e historico de melhorias.
- `agents/`
  - Prompts e instrucoes para agentes especializados.

## Frentes principais do sistema

1. Relatorios Promax
- Entry points reais: `entrypoints/reports/relatorios.py`, `entrypoints/reports/relatorios_fechamento.py` e `entrypoints/reports/repescagem_relatorios.py`.
- Orquestracao central em `core/services/report_orchestration_service.py`.
- Publicacao final e reprocessamento de pendencias em `core/services/publication_service.py`.

2. Digitacao de pedidos
- Entry point real: `entrypoints/processes/pedidos.py`.
- Rotina principal: `030104`.

3. Alteracao em lote de condicao/CEMC
- Entry point real: `entrypoints/processes/lote_condicao.py`.
- Rotina principal: `03030701`.

4. Utilitarios operacionais
- `entrypoints/maintenance/reprocessar_publicacao.py`
- `entrypoints/tools/mapeador.py`
- `entrypoints/reports/relatorio_140510.py`

## Como o projeto opera

Fluxo tipico dos relatorios:

1. abrir sessao via `core/execution/entrypoint_helpers.py`
2. fazer login no Promax
3. acessar a rotina pelo menu
4. executar a rotina com Page Object
5. capturar download na pasta intermediaria
6. registrar resultado no tracker
7. higienizar artefatos intermediarios
8. publicar para destino final
9. refletir sucesso, pendencia ou falha em `ExecutionResult`

## Particularidades tecnicas

- O Promax e um sistema legado com frames, alertas bloqueantes e comportamento DOM instavel.
- Interacoes de pagina dependem fortemente de JavaScript injetado e helpers de `RotinaPage`.
- `DOWNLOAD_DIR` e apenas a pasta intermediaria de captura.
- Parte do download ainda depende de automacao visual e da barra nativa do IE.
- O projeto precisa de Windows, desktop interativo e acesso a compartilhamentos de rede.

## Arquivos mais importantes para manutencao

- `core/config/settings.py`
- `core/config/project_paths.py`
- `core/execution/entrypoint_helpers.py`
- `core/services/report_orchestration_service.py`
- `core/services/publication_service.py`
- `core/files/movimentador.py`
- `core/files/manipulador_download.py`
- `core/observability/relatorio_execucao.py`
- `pages/auth/login_page.py`
- `pages/common/menu_page.py`
- `pages/common/rotina_page.py`
- `pages/reports/*.py`
- `entrypoints/reports/relatorios.py`
- `entrypoints/reports/relatorios_fechamento.py`
- `entrypoints/reports/repescagem_relatorios.py`

## Heuristica rapida

- Problema de login, sessao ou navegador:
  - olhar `core/browser/driver_factory.py`, `core/execution/entrypoint_helpers.py`, `pages/auth/login_page.py`
- Problema de fluxo geral de relatorios:
  - olhar `core/services/report_orchestration_service.py` e o entrypoint correspondente em `entrypoints/`
- Problema de download e publicacao:
  - olhar `core/services/report_download_service.py`, `core/files/manipulador_download.py`, `core/files/movimentador.py`, `core/services/publication_service.py`
- Problema de rotina especifica:
  - olhar `pages/reports/arquivo_da_rotina.py`

## Compatibilidade

Os arquivos da raiz `main.py`, `mainRelatorios.py`, `mainRelatoriosFechamento.py`, `mainPedidos.py`, `mainReprocessarPublicacao.py`, `main140510.py`, `mainMapeador.py` e `alterarCEMC.py` continuam existindo apenas como wrappers para preservar chamadas operacionais antigas.




