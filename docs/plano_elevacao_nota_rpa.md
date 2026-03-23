# Plano de ElevaÃ§Ã£o da Nota TÃ©cnica - Projeto RPA

## Objetivo
Este documento prioriza por onde comeÃ§ar as mudanÃ§as para elevar a nota tÃ©cnica do projeto com o maior ganho de robustez, previsibilidade operacional e capacidade de manutenÃ§Ã£o.

## 1. ComeÃ§ar pelo contrato real de sucesso e falha
Hoje o maior problema nÃ£o Ã© apenas falhar. Ã‰ falhar e o sistema considerar que deu certo.

### O que corrigir primeiro
- Fazer `executar_tarefa_com_retry()` em [mainRelatorios.py](C:/Users/caixa.patos/Documents/promax-web-driver/mainRelatorios.py#L92) respeitar o retorno das rotinas.
- Fazer cada rotina devolver status padronizado, nÃ£o apenas `True` ou `False`.
- Separar claramente:
- `SUCESSO`
- `SUCESSO PARCIAL`
- `FALHA DE NEGÃ“CIO`
- `FALHA TÃ‰CNICA`
- `ABORTADO`

### Por que comeÃ§ar aqui
- Esse ponto distorce toda a percepÃ§Ã£o de estabilidade do projeto.
- Sem isso, qualquer log, repescagem ou movimentaÃ§Ã£o de arquivo pode ser baseado em premissa errada.

### Ganho esperado
- ReduÃ§Ã£o imediata de falso positivo.
- Melhor leitura do que realmente quebrou.
- Base correta para todas as prÃ³ximas melhorias.

## 2. Corrigir timeouts tratados como sucesso
O segundo ponto mais grave Ã© a automaÃ§Ã£o avanÃ§ar sem confirmaÃ§Ã£o real.

### EvidÃªncia principal
- `executar_gatilho_e_aguardar()` retorna `True, "Timeout"` em [rotina_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/common/rotina_page.py#L480).

### O que fazer
- Timeout deve virar falha por padrÃ£o.
- SÃ³ considerar sucesso quando houver evidÃªncia objetiva:
- alerta de confirmaÃ§Ã£o
- botÃ£o habilitado/desabilitado conforme esperado
- mudanÃ§a de estado no DOM
- arquivo criado e validado

### Ganho esperado
- Elimina sucesso fictÃ­cio em rotinas crÃ­ticas.
- Aumenta robustez em processos como digitaÃ§Ã£o e alteraÃ§Ã£o de dados.

## 3. Reduzir dependÃªncia de automaÃ§Ã£o visual
O projeto usa abordagem visual porque o sistema Ã© legado, o que Ã© compreensÃ­vel. O problema Ã© tratar isso como mecanismo principal.

### EvidÃªncia principal
- [manipulador_download.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/files/manipulador_download.py#L12)
- [login_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/auth/login_page.py#L197)

### O que fazer
- Tornar o download orientado por diretÃ³rio configurado, nÃ£o por `Downloads` fixo.
- Validar arquivo por nome, tamanho estabilizado e extensÃ£o final.
- Manter `pyautogui` e reconhecimento visual apenas como fallback.
- Adicionar flag de modo de execuÃ§Ã£o:
- `modo_deterministico`
- `modo_visual_fallback`

### Ganho esperado
- Menos fragilidade em VM, RDP, desktop bloqueado e execuÃ§Ã£o recorrente.
- Ganho direto em robustez e prontidÃ£o para produÃ§Ã£o.

## 4. Trocar `sleep` por espera baseada em estado
O sistema hoje espera muito por tempo e pouco por condiÃ§Ã£o real.

### O que fazer
- Criar helpers reutilizÃ¡veis para:
- esperar loader sumir
- esperar campo habilitar
- esperar frame estabilizar
- esperar nova janela e handle consistentes
- esperar arquivo finalizar gravaÃ§Ã£o
- Substituir os `time.sleep()` mais crÃ­ticos primeiro:
- [login_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/auth/login_page.py)
- [menu_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/common/menu_page.py)
- [rotina_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/common/rotina_page.py)
- rotinas `0512`, `120616`, `150501`, `020220`

### Ganho esperado
- Menos timeout intermitente.
- Menos lentidÃ£o artificial.
- Comportamento mais previsÃ­vel em produÃ§Ã£o.

## 5. Parar de esconder erro importante
Hoje hÃ¡ muitos pontos onde o sistema ignora falhas e segue.

### EvidÃªncia principal
- [login_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/auth/login_page.py#L129)
- [rotina_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/common/rotina_page.py#L39)
- [driver_factory.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/browser/driver_factory.py#L29)

### O que fazer
- Revisar `except: pass`.
- Substituir por uma destas opÃ§Ãµes:
- logar e seguir, quando for realmente seguro
- logar e retentar
- logar e abortar a unidade
- logar e abortar a execuÃ§Ã£o

### Ganho esperado
- DiagnÃ³stico mais confiÃ¡vel.
- Menos inconsistÃªncia silenciosa.

## 6. Criar validaÃ§Ãµes determinÃ­sticas pÃ³s-aÃ§Ã£o
Toda aÃ§Ã£o crÃ­tica precisa confirmar que o efeito esperado aconteceu.

### Prioridade de validaÃ§Ã£o
- PÃ³s-login: confirmar menu real e campo `atalho`.
- PÃ³s-troca de unidade: confirmar unidade ativa.
- PÃ³s-visualizar: confirmar tela de exportaÃ§Ã£o.
- PÃ³s-download: confirmar arquivo final correto.
- PÃ³s-salvar processo: confirmar mensagem ou mudanÃ§a de estado.

### Ganho esperado
- ReduÃ§Ã£o de falha encadeada.
- Melhor rastreabilidade causal.

## 7. Organizar a configuraÃ§Ã£o do projeto
HÃ¡ muitos valores fixos em cÃ³digo.

### EvidÃªncia principal
- [mainPedidos.py](C:/Users/caixa.patos/Documents/promax-web-driver/mainPedidos.py#L46)
- [alterarCEMC.py](C:/Users/caixa.patos/Documents/promax-web-driver/alterarCEMC.py#L15)

### O que fazer
- Criar um mÃ³dulo de configuraÃ§Ã£o central.
- Mover para configuraÃ§Ã£o:
- caminhos de planilhas
- unidade padrÃ£o
- timeouts
- diretÃ³rios de download
- rotinas habilitadas
- destinos de movimentaÃ§Ã£o

### Ganho esperado
- Menos manutenÃ§Ã£o por ediÃ§Ã£o manual de script.
- Menos risco de erro ao trocar ambiente.

## 8. Unificar os entrypoints
O projeto ainda cresce por script raiz.

### O que fazer
- Criar uma CLI Ãºnica, por exemplo:
- `python app.py relatorios`
- `python app.py pedidos`
- `python app.py alterar-condicao`
- `python app.py mapear`
- Reaproveitar sessÃ£o, retry, logging e fechamento em um orquestrador comum.

### Ganho esperado
- Menos duplicaÃ§Ã£o.
- Menos divergÃªncia de comportamento.
- Mais clareza arquitetural.

## 9. Melhorar seguranÃ§a operacional do driver e arquivos

### Driver
- Evitar `taskkill` global em [driver_factory.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/browser/driver_factory.py#L17).
- Matar apenas processos do prÃ³prio robÃ´, quando possÃ­vel.

### Arquivos
- Implementar staging antes de sobrescrever em rede.
- Validar tamanho e disponibilidade do arquivo antes de mover.
- Registrar operaÃ§Ã£o de cÃ³pia/substituiÃ§Ã£o com mais detalhe.

### Ganho esperado
- Menos efeito colateral em mÃ¡quina compartilhada.
- Menor risco de perda de arquivo vÃ¡lido.

## 10. Introduzir testes mÃ­nimos
NÃ£o faz sentido tentar escalar manutenÃ§Ã£o sem ao menos teste de utilitÃ¡rio e contrato.

### ComeÃ§ar por
- `core/files/renomeador.py`
- `core/observability/relatorio_execucao.py`
- parsing de cÃ³digo de rotina
- classificaÃ§Ã£o de status
- geraÃ§Ã£o de nomes de arquivos

### Depois evoluir para
- smoke tests de pÃ¡ginas com mocks
- validaÃ§Ã£o de contrato das rotinas

### Ganho esperado
- Menos regressÃ£o em refatoraÃ§Ãµes.
- Mais seguranÃ§a para mexer no nÃºcleo.

## Ordem recomendada de execuÃ§Ã£o

### Fase 1: impacto imediato
- Corrigir contrato de sucesso/falha
- Corrigir timeout como falha
- Corrigir diretÃ³rio real de download
- Adicionar validaÃ§Ãµes pÃ³s-login e pÃ³s-download

### Fase 2: estabilizaÃ§Ã£o
- Reduzir `sleep`
- Revisar exceÃ§Ãµes suprimidas
- Melhorar logs de decisÃ£o e de falha
- Revisar movimentaÃ§Ã£o de arquivos

### Fase 3: estrutura
- Centralizar configuraÃ§Ã£o
- Unificar entrypoints
- Criar orquestrador comum
- Introduzir testes mÃ­nimos

## Meta realista de evoluÃ§Ã£o da nota
Se a Fase 1 for bem executada, a nota jÃ¡ tende a subir principalmente em:
- Robustez
- ProntidÃ£o para produÃ§Ã£o
- Observabilidade

Se Fase 1 e Fase 2 forem concluÃ­das com disciplina, o projeto pode sair da faixa 5,4 para algo entre 6,8 e 7,5.

Se a Fase 3 for implementada com consistÃªncia, o projeto passa a ter base para disputar nota acima de 8 em contexto de RPA corporativo legado.

## ConclusÃ£o
O primeiro movimento nÃ£o deve ser â€œrefatorar tudoâ€. Deve ser eliminar mentira operacional.

Enquanto o projeto ainda puder registrar sucesso sem comprovar sucesso, qualquer melhoria estrutural posterior serÃ¡ construÃ­da sobre uma base enganosa. O melhor ponto de partida Ã© corrigir a semÃ¢ntica de execuÃ§Ã£o, validar estados crÃ­ticos e reduzir dependÃªncia visual. Isso aumenta a nota mais rÃ¡pido e, principalmente, aumenta a confianÃ§a real no robÃ´.



