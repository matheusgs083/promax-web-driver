# Code Review Tecnico - 2026-03-23

## Findings

### 1. Critico: o download continua acoplado a UI nativa e a `Downloads` do perfil do Windows

- Evidencia: [core/files/manipulador_download.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/files/manipulador_download.py#L46), [core/files/manipulador_download.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/files/manipulador_download.py#L74), [core/files/manipulador_download.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/files/manipulador_download.py#L82), [core/files/manipulador_download.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/files/manipulador_download.py#L137)
- Problema: o fluxo ainda observa `Path.home()/Downloads`, depende de `pyautogui`, usa a barra nativa do IE e sincroniza parte do processo com `sleep` fixo.
- Risco pratico: variacao de foco de janela, RDP minimizado, latencia do SO ou perfil de usuario diferente continuam causando timeout falso, captura do arquivo errado ou falha de download mesmo quando a rotina gerou o CSV.
- Recomendacao: consolidar um contrato unico para origem de captura, reduzir o uso de automacao visual ao fallback real e isolar a deteccao de arquivo novo com criterio deterministico por nome/timestamp.

### 2. Alto: `140510` e `mapeador` ainda fogem do bootstrap padrao do projeto

- Evidencia: [entrypoints/reports/relatorio_140510.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/reports/relatorio_140510.py#L75), [entrypoints/reports/relatorio_140510.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/reports/relatorio_140510.py#L85), [entrypoints/reports/relatorio_140510.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/reports/relatorio_140510.py#L98), [entrypoints/tools/mapeador.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/tools/mapeador.py#L40), [entrypoints/tools/mapeador.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/tools/mapeador.py#L83)
- Problema: esses fluxos continuam abrindo driver, lendo credenciais e tratando retry localmente, sem usar `core/execution/entrypoint_helpers.py` nem a orquestracao comum.
- Risco pratico: correcoes de sessao, login, encerramento de driver e padronizacao de status nao se propagam automaticamente para esses dois fluxos.
- Recomendacao: migrar ambos para o mesmo bootstrap usado por `relatorios`, `pedidos` e `lote_condicao`, mesmo que a logica de negocio continue especifica.

### 3. Medio: os entrypoints de relatorios ainda carregam varias tarefas inativas no mesmo arquivo

- Evidencia: [entrypoints/reports/relatorios.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/reports/relatorios.py#L104), [entrypoints/reports/relatorios.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/reports/relatorios.py#L251), [entrypoints/reports/relatorios_fechamento.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/reports/relatorios_fechamento.py#L90), [entrypoints/reports/relatorios_fechamento.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/reports/relatorios_fechamento.py#L205)
- Problema: os modulos definem varias funcoes `tarefa_*`, mas os dicionarios `tarefas` ativam apenas uma parte desse conjunto.
- Risco pratico: a configuracao ativa fica pouco explicita, aumenta a area de leitura e facilita erro de manutencao ao alterar uma rotina que nem esta no plano atual de execucao.
- Recomendacao: extrair catalogos de tarefas por fluxo ou mover o plano ativo para um modulo declarativo de configuracao.

### 4. Medio: ainda existem `sleep`s em caminhos sensiveis do legado

- Evidencia: [pages/common/rotina_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/common/rotina_page.py#L153), [pages/common/rotina_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/common/rotina_page.py#L276), [pages/common/rotina_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/common/rotina_page.py#L579), [core/files/manipulador_download.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/files/manipulador_download.py#L77), [core/files/manipulador_download.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/files/manipulador_download.py#L87)
- Problema: parte do fluxo ainda depende de pausas fixas em vez de espera por estado observavel.
- Risco pratico: a automacao segue sensivel a desempenho de VM, rede, foco de tela e comportamento assincromo do Promax.
- Recomendacao: substituir `sleep` por polling de frame, alerta, DOM ou arquivo sempre que existir sinal confiavel.

### 5. Medio: ainda ha arquivos com encoding quebrado e texto corrompido

- Evidencia: [core/files/manipulador_download.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/files/manipulador_download.py#L39), [entrypoints/reports/relatorio_140510.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/reports/relatorio_140510.py#L24), [entrypoints/tools/mapeador.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/tools/mapeador.py#L21)
- Problema: existem comentarios, logs e strings com mojibake.
- Risco pratico: manutencao mais lenta, diffs piores e risco de patch em trecho errado.
- Recomendacao: padronizar UTF-8 limpo nos modulos legados restantes.

## Melhorias confirmadas nesta rodada

### Organizacao de projeto melhorou de forma concreta

- Evidencia: [entrypoints/README.md](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/README.md), [core/config/project_paths.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/config/project_paths.py), [cli.py](C:/Users/caixa.patos/Documents/promax-web-driver/cli.py)
- Ganho: a logica real dos executaveis saiu da raiz e passou a viver em `entrypoints/`, enquanto `main*.py` ficaram como wrappers de compatibilidade.
- Impacto: Alto

### Paths do projeto deixaram de depender do diretorio de execucao em parte critica

- Evidencia: [core/config/project_paths.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/config/project_paths.py), [core/files/movimentador.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/files/movimentador.py#L13), [entrypoints/reports/relatorios.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/reports/relatorios.py#L16), [entrypoints/reports/relatorios_fechamento.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/reports/relatorios_fechamento.py#L15), [entrypoints/reports/repescagem_relatorios.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/reports/repescagem_relatorios.py#L15)
- Ganho: logs, data e entrypoints principais agora usam root estavel do projeto em vez de `cwd`.
- Impacto: Alto

### Orquestracao de relatorios ficou mais governada

- Evidencia: [core/services/report_orchestration_service.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/services/report_orchestration_service.py), [core/services/publication_service.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/services/publication_service.py), [core/services/report_post_processing_service.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/services/report_post_processing_service.py)
- Ganho: execucao, repescagem, pos-processamento e publicacao agora tem separacao explicita e retorno consolidado.
- Impacto: Alto

### Status de publicacao e repescagem melhoraram

- Evidencia: [core/files/movimentador.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/files/movimentador.py), [core/services/publication_service.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/services/publication_service.py), [entrypoints/maintenance/reprocessar_publicacao.py](C:/Users/caixa.patos/Documents/promax-web-driver/entrypoints/maintenance/reprocessar_publicacao.py)
- Ganho: pendencia de publicacao agora e refletida no resultado, e existe reprocessador dedicado para `logs/publicacao_pendente`.
- Impacto: Alto

### Cobertura automatizada subiu nos pontos de controle

- Evidencia: [tests/core/test_entrypoint_helpers.py](C:/Users/caixa.patos/Documents/promax-web-driver/tests/core/test_entrypoint_helpers.py), [tests/core/test_report_orchestration_service.py](C:/Users/caixa.patos/Documents/promax-web-driver/tests/core/test_report_orchestration_service.py), [tests/core/test_publication_reprocessor.py](C:/Users/caixa.patos/Documents/promax-web-driver/tests/core/test_publication_reprocessor.py), [tests/core/test_movimentador.py](C:/Users/caixa.patos/Documents/promax-web-driver/tests/core/test_movimentador.py)
- Ganho: login, troca de unidade, retry, orquestracao e reprocessamento ja contam com regressao automatizada minima.
- Impacto: Medio/Alto

## Riscos prioritarios atuais

- Download visual ainda e o principal gargalo de confiabilidade.
- `140510` e `mapeador` ainda ficam fora do padrao de sessao/orquestracao.
- Os entrypoints de relatorios ainda misturam configuracao ativa com tarefas inativas no mesmo modulo.
- `sleep` fixo continua presente em partes do caminho critico.
- Ainda ha ruido de encoding em modulos legados.

## Nota tecnica atual

- Arquitetura: 7,6
- Robustez: 6,8
- Manutenibilidade: 7,2
- Clareza: 7,1
- Escalabilidade: 6,2
- Observabilidade: 8,2
- Prontidao para producao: 6,8

Nota geral atual: 7,1.

## Conclusao

A base ficou melhor organizada e mais coerente do que na rodada anterior. A migracao da logica real para `entrypoints/`, a introducao de `core/config/project_paths.py` e a consolidacao da orquestracao de relatorios reduziram ruido estrutural e corrigiram uma fonte real de erro operacional: dependencia de `cwd` em partes importantes do projeto.

O proximo salto de qualidade nao esta mais em organizacao de pasta. Ele esta concentrado em tres frentes objetivas: remover dependencia do download visual como caminho principal, alinhar `140510` e `mapeador` ao bootstrap comum e transformar os entrypoints de relatorio em configuracao declarativa em vez de arquivos com tarefas ativas e inativas misturadas.




