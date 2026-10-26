# NetMonitor

Sistema web local de conectividade para portfólio profissional de TI.
Use somente dispositivos próprios ou explicitamente autorizados.

## Funcionalidades concluídas

**Dia 1:** estrutura Flask, página inicial, arquivos estáticos e módulo de ping
seguro, com resultados estruturados e testes simulados.

**Dia 2:** SQLite, cadastro, listagem, consulta por ID, edição e exclusão com
confirmação; ping manual IPv4/IPv6 e domínios; última verificação e histórico;
validação, normalização e prevenção de duplicidade; proteção CSRF em todo POST.
Interface responsiva com fundo cinza-escuro, destaques laranja e textos claros.

Não há dashboard completo, gráficos, monitoramento automático, deploy no Render,
PostgreSQL ou autenticação. Nenhuma funcionalidade do Dia 3 foi implementada.

## Tecnologias e estrutura

Python 3.10+ (testes na nuvem em 3.12), Flask, SQLite (`sqlite3`), HTML e CSS.
Testes com `unittest` e mocks, sem dependências adicionais.

```text
netmonitor/
├── app.py                 # Factory Flask, rotas, CSRF e servidor local
├── database.py            # Inicialização, CRUD e histórico SQLite
├── monitor.py             # Validação e ping Windows/Linux
├── requirements.txt
├── .gitignore
├── README.md
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── device_form.html
│   ├── delete.html
│   └── history.html
├── static/
│   ├── css/style.css
│   └── js/main.js
├── tests/
│   ├── test_app.py
│   ├── test_monitor.py
│   ├── test_database.py
│   ├── test_devices_web.py
│   └── test_ipv6.py
└── instance/netmonitor.sqlite3  # Criado automaticamente; ignorado pelo Git
```

## Windows / VS Code

Instale Python 3.10+ e a extensão Python da Microsoft. Abra a pasta do projeto
no VS Code e execute no terminal PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Selecione `.venv\Scripts\python.exe` em **Python: Select Interpreter**.
No seu computador, abra `http://127.0.0.1:5000`. Encerre com Ctrl+C.
Opcionalmente ative o ambiente com `.\.venv\Scripts\Activate.ps1`.
Usar o interpretador diretamente evita alterar a política do PowerShell.

O servidor escuta apenas `127.0.0.1`, sem debug. Não o exponha publicamente nem
inicie Flask com `--host=0.0.0.0`. Não existe autenticação: o uso é local.
Cookies são HttpOnly e SameSite Strict; tokens CSRF estão vinculados à sessão.
Por padrão, a chave da sessão é aleatória a cada início: recarregue formulários
após reiniciar. Opcionalmente configure `NETMONITOR_SECRET_KEY` no ambiente com
uma chave privada forte e estável; nunca a versione.

## Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

O executável `ping` precisa estar no PATH para verificações reais. Windows
normalmente já o inclui. Em Debian/Ubuntu, um administrador pode instalar
`iputils-ping` pelo gerenciador de pacotes. A implementação Linux esperada é
iputils. Ausência do executável é exibida como `error` e registrada no histórico.

## Cadastro e verificação manual

1. Clique em **Adicionar dispositivo**.
2. Informe nome (1–100 caracteres), endereço, tipo e descrição opcional
   (até 1000 caracteres). Tipos: roteador, servidor, computador, impressora e outro.
3. Exemplos: `127.0.0.1`, `192.168.1.1`, `::1`, `2001:db8::1` ou `example.com`.
   `2001:db8::1` é endereço de documentação; não se espera resposta dele.
4. Clique em **Salvar**. Domínios são convertidos para minúsculas sem ponto final;
   IPv6 é normalizado. Endereços equivalentes não podem ser cadastrados novamente.
5. Clique em **Verificar agora**. Um único ping é executado e o resultado fica no
   cartão do dispositivo. **Histórico** exibe as 100 verificações mais recentes;
   registros anteriores continuam no banco.
6. Use **Editar** para alterar os dados. **Excluir** abre uma tela de confirmação:
   marque a caixa e confirme para remover o dispositivo e todo seu histórico.

Nenhum ping é iniciado ao abrir a página. POSTs inválidos ou sem token CSRF são
rejeitados, e GET não executa verificações nem altera dados.

## Persistência

O banco é inicializado automaticamente com `CREATE TABLE IF NOT EXISTS`, sem
apagar dados. Todas as conexões habilitam chaves estrangeiras; exclusão usa
`ON DELETE CASCADE`. Há índices por dispositivo/data e por data. Datas são UTC
com offset explícito `+00:00`. As consultas com entradas usam parâmetros SQL.
O arquivo fica em `instance/`, ignorado pelo Git, assim como arquivos auxiliares
SQLite. Faça backup local do banco com o servidor parado.

`create_app({"DATABASE": caminho})` permite um banco separado para testes.
`database.py` expõe `init_db`, `save_device` (criar/editar), `list_devices`,
`get_device`, `delete_device`, `record_check` e `get_history`.
IDs inexistentes nas rotas retornam 404; validação e duplicidade retornam 400.
Editar o endereço mantém o histórico anterior vinculado ao mesmo dispositivo;
para preservar a identidade de um destino antigo, cadastre outro dispositivo.

## Conectividade e IPv6

`check_connectivity(target, timeout=2.0)` aceita IPv4, IPv6 sem identificador de
interface e hostname DNS ASCII (incluindo `localhost`). Rejeita URLs, portas,
CIDR, IPv6 entre colchetes, espaços, opções de comando e entradas malformadas.
Não remove espaços de destinos silenciosamente.

O subprocesso recebe uma lista de argumentos, sem shell, um pacote e prazo de
execução. Endereços IPv6 usam `-6`; IPv4 e domínios usam `-4`, preservando o
comportamento de domínios do Dia 1. Portanto, domínio somente AAAA ainda não tem
fallback automático para IPv6. Windows usa `-n 1 -w <milissegundos>` e Linux usa
`-n -c 1 -W <segundos>`. Timeout deve ser finito, maior que zero e até 60 segundos.

O formato de retorno do Dia 1 foi preservado:

```python
{
    "target": "::1",
    "status": "online",
    "latency_ms": 1.0,
    "latency_is_upper_bound": True,
    "error": None,
}
```

Exemplo ilustrativo, não uma medição real. Status: `online`, `offline`, `timeout`
ou `error`; latência indisponível é `None`. Respostas `<1ms` preservam o limite
superior, sem inventar uma medição exata. Falhas de DNS reconhecidas e falhas de
execução retornam `error`. Saídas de timeout e subprocesso expirado retornam
`timeout`. Destino inacessível pode ser `offline`.

## Testes

Na raiz do projeto, no Windows:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

No Linux:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
```

A suíte usa bancos temporários e mocks de ping, sem consultar dispositivos
externos. Cobre o Dia 1, inicialização idempotente, CRUD, validação, duplicidade,
SQL parametrizado, chaves estrangeiras/cascata, histórico e datas UTC, rotas,
CSRF (ausente, inválido e de outra sessão), escape HTML, ping IPv4/IPv6,
timeout, DNS e ausência do executável. A expectativa antiga que rejeitava `::1`
foi atualizada, pois agora esse endereço é suportado.

## Limitações e validação local

- IPv6 Windows/Linux é coberto por simulação automatizada; valide ping real de
  `::1` e dos seus dispositivos autorizados no Windows antes de assumir suporte
  operacional na sua rede. IPv6, firewall e ICMP precisam estar disponíveis.
- O ambiente de nuvem não inclui `ping`; testes simulados e Flask funcionam,
  mas isso não comprova envio real de pacotes IPv4/IPv6 nesse ambiente.
- Ping bloqueado não prova que o dispositivo está desligado. O reconhecimento
  textual cobre saídas comuns em português/inglês; outros idiomas e erros de
  DNS não reconhecidos podem resultar em classificação diferente.
- Endereços IPv6 link-local com escopo (`fe80::1%eth0`) não são aceitos.
- Verificações são síncronas e manuais. O servidor de desenvolvimento não é
  destinado a carga alta ou exposição pública.
