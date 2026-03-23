# Plano de Elevação da Nota Técnica - Projeto RPA

## Objetivo
Este documento prioriza por onde começar as mudanças para elevar a nota técnica do projeto com o maior ganho de robustez, previsibilidade operacional e capacidade de manutenção.

## 1. Começar pelo contrato real de sucesso e falha
Hoje o maior problema não é apenas falhar. É falhar e o sistema considerar que deu certo.

### O que corrigir primeiro
- Fazer `executar_tarefa_com_retry()` em [mainRelatorios.py](C:/Users/caixa.patos/Documents/promax-web-driver/mainRelatorios.py#L92) respeitar o retorno das rotinas.
- Fazer cada rotina devolver status padronizado, não apenas `True` ou `False`.
- Separar claramente:
- `SUCESSO`
- `SUCESSO PARCIAL`
- `FALHA DE NEGÓCIO`
- `FALHA TÉCNICA`
- `ABORTADO`

### Por que começar aqui
- Esse ponto distorce toda a percepção de estabilidade do projeto.
- Sem isso, qualquer log, repescagem ou movimentação de arquivo pode ser baseado em premissa errada.

### Ganho esperado
- Redução imediata de falso positivo.
- Melhor leitura do que realmente quebrou.
- Base correta para todas as próximas melhorias.

## 2. Corrigir timeouts tratados como sucesso
O segundo ponto mais grave é a automação avançar sem confirmação real.

### Evidência principal
- `executar_gatilho_e_aguardar()` retorna `True, "Timeout"` em [rotina_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/rotina_page.py#L480).

### O que fazer
- Timeout deve virar falha por padrão.
- Só considerar sucesso quando houver evidência objetiva:
- alerta de confirmação
- botão habilitado/desabilitado conforme esperado
- mudança de estado no DOM
- arquivo criado e validado

### Ganho esperado
- Elimina sucesso fictício em rotinas críticas.
- Aumenta robustez em processos como digitação e alteração de dados.

## 3. Reduzir dependência de automação visual
O projeto usa abordagem visual porque o sistema é legado, o que é compreensível. O problema é tratar isso como mecanismo principal.

### Evidência principal
- [manipulador_download.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/manipulador_download.py#L12)
- [login_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/login_page.py#L197)

### O que fazer
- Tornar o download orientado por diretório configurado, não por `Downloads` fixo.
- Validar arquivo por nome, tamanho estabilizado e extensão final.
- Manter `pyautogui` e reconhecimento visual apenas como fallback.
- Adicionar flag de modo de execução:
- `modo_deterministico`
- `modo_visual_fallback`

### Ganho esperado
- Menos fragilidade em VM, RDP, desktop bloqueado e execução recorrente.
- Ganho direto em robustez e prontidão para produção.

## 4. Trocar `sleep` por espera baseada em estado
O sistema hoje espera muito por tempo e pouco por condição real.

### O que fazer
- Criar helpers reutilizáveis para:
- esperar loader sumir
- esperar campo habilitar
- esperar frame estabilizar
- esperar nova janela e handle consistentes
- esperar arquivo finalizar gravação
- Substituir os `time.sleep()` mais críticos primeiro:
- [login_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/login_page.py)
- [menu_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/menu_page.py)
- [rotina_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/rotina_page.py)
- rotinas `0512`, `120616`, `150501`, `020220`

### Ganho esperado
- Menos timeout intermitente.
- Menos lentidão artificial.
- Comportamento mais previsível em produção.

## 5. Parar de esconder erro importante
Hoje há muitos pontos onde o sistema ignora falhas e segue.

### Evidência principal
- [login_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/login_page.py#L129)
- [rotina_page.py](C:/Users/caixa.patos/Documents/promax-web-driver/pages/rotina_page.py#L39)
- [driver_factory.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/driver_factory.py#L29)

### O que fazer
- Revisar `except: pass`.
- Substituir por uma destas opções:
- logar e seguir, quando for realmente seguro
- logar e retentar
- logar e abortar a unidade
- logar e abortar a execução

### Ganho esperado
- Diagnóstico mais confiável.
- Menos inconsistência silenciosa.

## 6. Criar validações determinísticas pós-ação
Toda ação crítica precisa confirmar que o efeito esperado aconteceu.

### Prioridade de validação
- Pós-login: confirmar menu real e campo `atalho`.
- Pós-troca de unidade: confirmar unidade ativa.
- Pós-visualizar: confirmar tela de exportação.
- Pós-download: confirmar arquivo final correto.
- Pós-salvar processo: confirmar mensagem ou mudança de estado.

### Ganho esperado
- Redução de falha encadeada.
- Melhor rastreabilidade causal.

## 7. Organizar a configuração do projeto
Há muitos valores fixos em código.

### Evidência principal
- [mainPedidos.py](C:/Users/caixa.patos/Documents/promax-web-driver/mainPedidos.py#L46)
- [alterarCEMC.py](C:/Users/caixa.patos/Documents/promax-web-driver/alterarCEMC.py#L15)

### O que fazer
- Criar um módulo de configuração central.
- Mover para configuração:
- caminhos de planilhas
- unidade padrão
- timeouts
- diretórios de download
- rotinas habilitadas
- destinos de movimentação

### Ganho esperado
- Menos manutenção por edição manual de script.
- Menos risco de erro ao trocar ambiente.

## 8. Unificar os entrypoints
O projeto ainda cresce por script raiz.

### O que fazer
- Criar uma CLI única, por exemplo:
- `python app.py relatorios`
- `python app.py pedidos`
- `python app.py alterar-condicao`
- `python app.py mapear`
- Reaproveitar sessão, retry, logging e fechamento em um orquestrador comum.

### Ganho esperado
- Menos duplicação.
- Menos divergência de comportamento.
- Mais clareza arquitetural.

## 9. Melhorar segurança operacional do driver e arquivos

### Driver
- Evitar `taskkill` global em [driver_factory.py](C:/Users/caixa.patos/Documents/promax-web-driver/core/driver_factory.py#L17).
- Matar apenas processos do próprio robô, quando possível.

### Arquivos
- Implementar staging antes de sobrescrever em rede.
- Validar tamanho e disponibilidade do arquivo antes de mover.
- Registrar operação de cópia/substituição com mais detalhe.

### Ganho esperado
- Menos efeito colateral em máquina compartilhada.
- Menor risco de perda de arquivo válido.

## 10. Introduzir testes mínimos
Não faz sentido tentar escalar manutenção sem ao menos teste de utilitário e contrato.

### Começar por
- `core/renomeador.py`
- `core/relatorio_execucao.py`
- parsing de código de rotina
- classificação de status
- geração de nomes de arquivos

### Depois evoluir para
- smoke tests de páginas com mocks
- validação de contrato das rotinas

### Ganho esperado
- Menos regressão em refatorações.
- Mais segurança para mexer no núcleo.

## Ordem recomendada de execução

### Fase 1: impacto imediato
- Corrigir contrato de sucesso/falha
- Corrigir timeout como falha
- Corrigir diretório real de download
- Adicionar validações pós-login e pós-download

### Fase 2: estabilização
- Reduzir `sleep`
- Revisar exceções suprimidas
- Melhorar logs de decisão e de falha
- Revisar movimentação de arquivos

### Fase 3: estrutura
- Centralizar configuração
- Unificar entrypoints
- Criar orquestrador comum
- Introduzir testes mínimos

## Meta realista de evolução da nota
Se a Fase 1 for bem executada, a nota já tende a subir principalmente em:
- Robustez
- Prontidão para produção
- Observabilidade

Se Fase 1 e Fase 2 forem concluídas com disciplina, o projeto pode sair da faixa 5,4 para algo entre 6,8 e 7,5.

Se a Fase 3 for implementada com consistência, o projeto passa a ter base para disputar nota acima de 8 em contexto de RPA corporativo legado.

## Conclusão
O primeiro movimento não deve ser “refatorar tudo”. Deve ser eliminar mentira operacional.

Enquanto o projeto ainda puder registrar sucesso sem comprovar sucesso, qualquer melhoria estrutural posterior será construída sobre uma base enganosa. O melhor ponto de partida é corrigir a semântica de execução, validar estados críticos e reduzir dependência visual. Isso aumenta a nota mais rápido e, principalmente, aumenta a confiança real no robô.
