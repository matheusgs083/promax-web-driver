# Cora Web Driver

Driver isolado para o portal Cora, executado pelo mesmo worker de jobs do
`promax-web-driver`. O subprojeto não reutiliza os page objects do Promax: o
Cora é uma aplicação web moderna e terá sessão, seletores e fluxos próprios.

## Estado atual

O CLI fornece a entrada controlada para o worker e um comando `health` para
validar a configuração sem abrir o navegador. Os fluxos de negócio devem ser
adicionados como operações explícitas depois de definir qual rotina do Cora
será automatizada primeiro.

## Configuração

- `CORA_URL` (padrão: `https://cora.ab-inbev.com/?redirectTo=%2F`)
- `CORA_HEADLESS` (`0` por padrão durante a homologação)
- `CORA_RUNTIME_USER` e `CORA_RUNTIME_PASS` são recebidos somente no processo
  filho do worker; nunca entram no comando ou nos logs.

## Uso manual

```powershell
python cli.py health
python cli.py executar --operacao <operacao> --job-id <id>
python cli.py executar --operacao abrir_revenda --job-id <id>
```

`abrir_revenda` cria um perfil descartável, limpa cookies, seleciona Brasil e
acessa o perfil Revenda. O comando `executar` falha de forma explícita para
operações que ainda não possuem implementação, evitando marcar um job como
concluído sem executar o fluxo real.
