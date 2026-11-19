# 03.01.04 — Digitação de pedidos por HTTP: o que implementar

Documento para quem vai ligar a digitação da 03.01.04 ao worker. A parte de
Promax já existe e foi testada de verdade (pedido **015633**, mapa **096721**,
Patos, 18/11/2026). Falta transformar o teste de um pedido num job do worker
que digita uma lista de pedidos.

Nada aqui usa navegador: é o mesmo cliente HTTP (`promax_http`) dos relatórios.

---

## 1. O que já existe (não reescrever)

| Arquivo | O que tem |
|---|---|
| `promax_http/pedido_030104.py` | Digitação de **um** pedido de ponta a ponta. Classe `Digitacao` (envia cada passo e lê a resposta), `item_lista()` (formato de 139 posições do campo `itensLista`), `formatar_ttv()`, `catalogo()` e `gravar_catalogo()`. CLI de teste: `testar_pedido_030104.bat`. |
| `promax_http/explorar_030104.py` | `podar_ramos()` e `valores_da_resposta()`: leem o JavaScript que o Promax devolve e aplicam só o que o navegador executaria (avaliam `if` com literais e com campos da tela). **Sem isso o robô vê alertas e perguntas que nunca aparecem na tela.** |
| `promax_http/html.py` | `opcoes_carregadas()`: lê as listas que o Promax preenche (`CCmbcdCondicaoPagto("408","408 - BOLETO ...")`). |
| `promax_http/cliente.py` | `Rotina.carga_frame9`: JavaScript da carga do frame 9 ao abrir a rotina (de onde sai a lista de condições). |
| `tests/promax_http/test_030104.py` | Testes das peças acima. |

Use essas peças. O que falta é o **laço de vários pedidos**, o **contrato de entrada e saída** e a **ligação com o worker**.

---

## 2. Como a tela funciona (o que o robô repete)

Cada passo é um POST no **frame 9** da rotina com o formulário inteiro e um `opcao`.
A resposta é JavaScript que preenche os campos da tela; o robô aplica essas
atribuições no formulário que manda no passo seguinte.

| Passo | `opcao` | Campos que o robô preenche | Observação |
|---|---|---|---|
| Mapa | 2 | `nrMapa` | `0` = o Promax gera um mapa novo e devolve o número (`096721`). Também devolve Tipo de Mapa = 0 (Automático), Gerar Carregamento = N e motivo vazio — é o padrão do próprio Promax; **não exigir motivo**. |
| Vendedor | 11 | `cdVendedor` | |
| Operação | 4 | `cdOperacao` = **1** (sempre) | Devolve tipo de movimento `051` (venda) e **libera** a condição de pagamento. |
| Cliente | 5 | `cdDestinatario` | Devolve a **condição padrão do cliente** (`cdCondicaoPagto`), tabela de preço, transportadora etc. Pode travar a condição (cliente inadimplente). |
| Liberar itens | 8 | — | |
| Adicionar item | 7 | `codProduto`, `qtPedida`, `idUnidade=N`, `vlAliquota=""`, `vlFCI=""`, `itensLista` (itens já aceitos), `carregando=1` | É o "check" à direita do item. Resposta boa chama `addList()` / `AdicionaLista` e traz nome do produto, unidade (`cx`) e o preço (`valorTTV`). **Um POST por item.** |
| Salvar | 6 | `itensLista` com **todos** os itens (`item_lista()` de cada um, concatenados), `idEnviaRoad=S` | Resposta: `alert('Pedido 015633 gerado, ...')`. Depois disso o Promax recarrega a tela inteira: **não** tratar os textos de `alert()` dentro das funções dela como erro; procurar só `Pedido (\d+) gerado`. |

Os passos 12 e 13 (validar produto e quantidade) estão desligados na própria tela; não usar.

---

## 3. Regras de negócio definidas

1. **Operação é sempre 1** (venda). Não vem da plataforma; fica fixa no código.
2. **Preço é fixo, pela tabela de preço do Promax.** A plataforma **não manda preço**. O robô envia o item **sem TTV** e lê o preço que o Promax aplicou na resposta do `opcao 7`
   (`valorTTV ... FormataCampo( '000000000044,00', ...)` → `44,00`) para devolver no resultado.
   ⚠ No teste o TTV foi enviado (44,00) e a tela mostrou 45,00 depois. **Validar no primeiro teste sem TTV** que o preço gravado é o da tabela.
3. **Vários pedidos no mesmo mapa:** digita o primeiro pedido com mapa `0`, salva, e **segue na mesma tela** para o próximo: o mapa continua; só muda vendedor, cliente, condição e itens (recomeça do `opcao 11`). Confirmado na operação manual; **validar por HTTP** no primeiro teste com 2 pedidos.
4. **Mapa existente:** se a plataforma mandar um número de mapa, o primeiro pedido daquele grupo envia o número no `opcao 2` (carrega o mapa) e os demais seguem como no item 3.
5. **Condição de pagamento:**
   - vazia → usa a padrão do cliente (vem no `opcao 5`);
   - preenchida → precisa estar na lista lida da unidade; se o Promax travou o campo (`cdCondicaoPagto.disabled = true` na resposta podada) e a pedida for diferente da padrão, **o pedido falha** com a padrão no motivo. Nunca forçar.
6. **Produto repetido no mesmo pedido** → o Promax recusa ("Código do produto já consta na lista"). Validar antes e recusar o pedido (ou somar quantidades, se a plataforma preferir — decidir).
7. **Limite de 200 itens por pedido** (limite da tela).
8. **Lista de condições:** a cada job, ler de `rotina.carga_frame9` e gravar com `gravar_catalogo()` em `data/catalogos/030104_condicoes_<unidade>.json` (só sobrescreve se veio preenchida). Devolver também no resultado do job. A plataforma lê esse arquivo para montar as opções. A lista inclui os códigos 051–070 (tipos de movimento); como a operação é sempre venda, a plataforma pode escondê-los.

---

## 4. Contrato do job

### Entrada (`payload.digitacao`, gravado pelo runner em `data/job_inputs/digitacao_030104_<job_id>.json`)

```json
{
  "unidade": "2210003",
  "pedidos": [
    {
      "ref": "plataforma-123",
      "mapa": "NOVO1",
      "vendedor": "992",
      "cliente": "16883",
      "cond_pagto": "",
      "itens": [
        {"produto": "2349", "quantidade": 2},
        {"produto": "2319", "quantidade": 5}
      ]
    }
  ]
}
```

- `ref`: identificador da plataforma, devolvido no resultado (é o que liga pedido da plataforma ↔ pedido do Promax).
- `mapa`: número de mapa existente **ou** etiqueta de mapa novo (`NOVO1`, `NOVO2`...). Pedidos com a mesma etiqueta vão para o mesmo mapa gerado. A ordem dos pedidos na lista é a ordem de digitação; agrupar por mapa antes de digitar.
- `cond_pagto`: opcional (vazio = padrão do cliente).
- Sem preço, sem operação (ver regras 1 e 2).

### Saída (no `metadata` do evento `promax_job_result`)

```json
{
  "mapas": {"NOVO1": "096721"},
  "pedidos": [
    {
      "ref": "plataforma-123",
      "status": "salvo",
      "pedido": "015633",
      "mapa": "096721",
      "condicao_padrao_cliente": "408",
      "condicao_usada": "408",
      "condicao_travada": false,
      "itens": [{"produto": "2349", "descricao": "GCA PT2 CX6", "quantidade": 2, "unidade": "cx", "preco": "44,00"}],
      "motivo": ""
    }
  ],
  "catalogo": {"unidade": "2210003", "lido_em": "...", "condicoes": [{"codigo": "408", "descricao": "BOLETO 8 DIAS 2,5%"}]}
}
```

`status` por pedido: `salvo`, `recusado` (validação antes do Promax ou Promax recusou; `motivo` com o texto) ou `nao_digitado` (job parou antes). Status do job: sucesso se todos salvos; sucesso parcial se algum falhou.

---

## 5. Onde ligar no projeto (seguir o padrão do `lancamento_grade`)

1. **`workers/promax_runner.py` → `build_command`**: novo `job_type`/`operation` `digitacao_030104`, igual ao bloco de `lancamento_grade`: validar `payload.digitacao`, gravar em `data/job_inputs/digitacao_030104_<job_id>.json` e montar
   `python cli.py digitacao-030104 --arquivo <json> --job-id <id> [--unidade X]`.
2. **`cli.py`**: registrar o comando `digitacao-030104` em `COMMANDS` (módulo novo, ex.: `entrypoints/processes/digitacao_030104.py`), com `--arquivo`, `--unidade`, `--job-id`, `--nao-salvar`; incluir na lista de jobs controlados para emitir `promax_job_result`.
3. **Entrypoint novo** (`entrypoints/processes/digitacao_030104.py`): lê e valida o JSON, abre **uma** sessão HTTP (`ClientePromax` + login na unidade), abre a 030104 **uma vez**, grava o catálogo e digita os pedidos em sequência usando a `Digitacao` de `pedido_030104.py`. Devolve `ExecutionResult` com o `metadata` do item 4.
4. **Laço dos pedidos** (o que é novo):
   - agrupar por `mapa`; para cada grupo, primeiro pedido com `nrMapa` = número ou `0` (etiqueta), guardar o mapa gerado em `mapas[etiqueta]`;
   - por pedido: `opcao 11 → 4 → 5 → (condição) → 8 → 7 por item → 6`;
   - depois do `opcao 6`, aplicar a resposta (podada) no formulário, limpar os campos do pedido anterior (cliente, itens, `itensLista`, `nrPedido`) e seguir para o próximo pedido **a partir do `opcao 11`**, mantendo `nrMapa`.
5. **Falha no meio de um pedido** (alerta, pergunta, item recusado): marcar o pedido como `recusado` com o texto do Promax e **reabrir a rotina** (`fechar_rotina` + `abrir_rotina`), recarregar o mapa do grupo pelo número (`opcao 2`) e continuar com o próximo pedido. Não tentar "consertar" o pedido na mesma tela.

---

## 6. Cuidados obrigatórios

- **Não repetir pedido salvo.** O job grava dado no Promax: **sem retry automático** depois que qualquer pedido foi salvo (o retry/repescagem dos relatórios não serve aqui). Emitir `promax_partial_result` a cada pedido salvo (ref + número) para que, se o processo cair, a plataforma saiba o que já entrou e não reenvie.
- **Uma sessão por usuário no Promax:** o job não pode rodar em paralelo com outro job Promax do mesmo usuário (o worker já serializa; manter assim).
- **Não tratar como erro** os `alert()` que só existem dentro de `if` falsos ou dentro de funções da tela: sempre passar a resposta por `podar_ramos(texto, form)` antes de procurar alertas/perguntas (`msgbxSimNao`, `confirm`). Pergunta real que aparecer → parar o pedido e devolver o texto (não responder "Sim" por conta própria, exceto o "Enviar ao Roteirizador?", que é sempre Sim).
- **Rastro:** usar `Transporte(pasta_rastro=...)` como no teste; é o que permite diagnosticar qualquer recusa.
- **`--nao-salvar`:** faz tudo até o `opcao 7` de cada item e não envia o `opcao 6`. Usar para homologar a plataforma sem criar pedido.

---

## 7. Testes antes de liberar

1. **Unitários** (sem Promax): agrupamento por mapa, validação do JSON (produto repetido, >200 itens, campos faltando), montagem do `itensLista` com vários itens, extração do preço da resposta do `opcao 7`, montagem do `metadata`. Usar as respostas reais guardadas em `logs/promax_http/20261118_192621_pedido_030104/` como fixtures.
2. **Real, sem salvar:** 2 pedidos, 2 itens cada, `--nao-salvar`.
3. **Real, salvando:** 2 pedidos no mesmo mapa novo (`NOVO1`), cliente 16883, setor 992, **sem preço** → conferir na tela: os dois no mesmo mapa e preço = tabela.
4. Cancelar no Promax os pedidos de teste (incluindo o **015633 / mapa 096721**).
