# NetMonitor

Sistema web de monitoramento de redes para portfólio profissional de TI.
O objetivo futuro é apresentar dispositivos, conectividade, latência e histórico.
**Dia 1:** estrutura, página inicial Flask e verificação pontual por ping.
Não há banco de dados, CRUD, dashboard, gráficos ou monitoramento automático.

## Tecnologias

Python 3.10+ (validado em 3.12), Flask, HTML, CSS e JavaScript.
Os testes usam `unittest` e `unittest.mock` da biblioteca padrão.
SQLite está previsto para etapas futuras e não é usado neste dia.

## Estrutura

```text
netmonitor/
├── app.py
├── monitor.py
├── requirements.txt
├── .gitignore
├── README.md
├── templates/
│   └── index.html
├── static/
│   ├── css/style.css
│   └── js/main.js
└── tests/
    ├── test_app.py
    └── test_monitor.py
```

## Instalação no Windows / VS Code

Instale Python 3.10+ e a extensão Python da Microsoft no VS Code.
Abra a pasta do repositório e execute no terminal PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Selecione `.venv\Scripts\python.exe` em **Python: Select Interpreter**.
Acesse `http://127.0.0.1:5000` no seu computador. Encerre com Ctrl+C.
O servidor é apenas para desenvolvimento local; debug está desativado.

Se a política do PowerShell bloquear a ativação, use diretamente o interpretador,
sem alterar a política de segurança:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Para conectividade real, o executável `ping` deve estar no PATH.
Windows normalmente já o inclui. Em Debian/Ubuntu, um administrador pode instalar
`iputils-ping` com `apt-get install iputils-ping`. Outros Linux podem usar seu
próprio gerenciador de pacotes. O módulo requer a implementação Linux iputils.
Na máquina de nuvem deste Dia 1, `ping` está ausente e a instalação global não
foi permitida. Isso não impede os testes simulados nem o servidor Flask.

## Testes

Com o ambiente virtual ativo, na raiz do projeto:

```bash
python -m unittest discover -s tests -v
python -m pip check
```

Os testes não enviam pacotes: simulam `subprocess.run` para cobrir sucesso,
falha, timeout, comando ausente, validação e diferenças Windows/Linux.
A página inicial e seus arquivos estáticos são verificados com o cliente Flask.

## Módulo de conectividade

`check_connectivity(target, timeout=2.0)` em `monitor.py` aceita IPv4 ou domínio
ASCII (incluindo localhost). IPv6, URLs, espaços e opções de comando são rejeitados
com `ValueError`; timeout deve ser finito, maior que zero e de até 60 segundos.
Use somente destinos próprios ou explicitamente autorizados.

O retorno é um dicionário, pronto para futura integração com Flask:

```python
{
    "target": "127.0.0.1",
    "status": "online",
    "latency_ms": 0.1,
    "latency_is_upper_bound": False,
    "error": None,
}
```

Esse exemplo ilustra o formato; não é uma medição real. Os status possíveis são
`online`, `offline`, `timeout` e `error`. A latência ausente é `None`.
Respostas `<1ms` retornam `1.0` com `latency_is_upper_bound=True`, sem inventar
uma medição exata. O subprocesso usa lista de argumentos, sem shell, um pacote
IPv4 e prazo de execução. Falhas de DNS podem aparecer como `offline` ou `error`,
conforme o código retornado pelo ping do sistema.

Ping bloqueado por firewall não prova que o dispositivo está desligado.
A interpretação textual cobre saídas comuns em inglês e português; outros
idiomas podem exigir adaptação. Compatibilidade Windows é testada por simulação,
sem execução em uma máquina Windows nesta etapa.

## Escopo concluído

- [x] Estrutura inicial e ambiente virtual.
- [x] Página Flask simples.
- [x] Conectividade pontual segura e resultados estruturados.
- [x] Testes automatizados sem dispositivos externos.
- [x] Instruções Windows PowerShell, Linux e VS Code.

Não há deploy, Render ou PostgreSQL configurados.
