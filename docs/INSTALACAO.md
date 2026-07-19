# Instalação — passo a passo

Este guia leva você do zero até o primeiro raio-x de um fundo, mesmo que
nunca tenha usado Python. Se algo der errado, veja os
[problemas comuns](#problemas-comuns) no final.

> **Só quer consultar os fundos?** Você não precisa instalar nada: o site
> **https://ruamms.github.io/scout/** tem o raio-x de todos os FIIs,
> atualizado diariamente. Instale localmente se quiser rodar as análises na
> sua máquina, usar a IA local ou contribuir com o projeto.

## O que você precisa

| Requisito | Para quê | Obrigatório? |
|---|---|---|
| Windows, Linux ou macOS | — | sim |
| [Python 3.11 ou mais novo](https://www.python.org/downloads/) | rodar o programa | sim |
| [Git](https://git-scm.com/downloads) | baixar o projeto (dá para baixar ZIP sem ele) | não |
| Internet | baixar os dados oficiais da CVM (~20 MB na 1ª vez) | sim |
| [Ollama](https://ollama.com) + GPU com 8 GB+ de VRAM | leitura de relatórios por IA (opcional) | não |
| Node.js | só para desenvolvedores rodarem os testes do JavaScript | não |

## Passo a passo (Windows)

**1. Instale o Python** — baixe em https://www.python.org/downloads/ e, na
primeira tela do instalador, **marque a caixa "Add python.exe to PATH"**
antes de clicar em Install. (Alternativa: `winget install Python.Python.3.11`.)

**2. Baixe o projeto** — escolha um dos dois jeitos:

- Com Git: abra o Prompt de Comando (tecla Windows, digite `cmd`) e rode:

  ```
  git clone https://github.com/Ruamms/scout.git
  cd scout
  ```

- Sem Git: em https://github.com/Ruamms/scout clique no botão verde
  **Code → Download ZIP**, extraia o ZIP e abra o Prompt de Comando dentro
  da pasta extraída (na barra de endereço do Explorer, digite `cmd` e Enter).

**3. Instale as dependências** — dentro da pasta do projeto:

```
pip install uv
uv sync
```

(`uv` é o gerenciador que cria um ambiente isolado — nada é instalado no
Python do sistema.)

**4. Baixe os dados oficiais e faça o primeiro raio-x:**

```
uv run scout atualizar
uv run scout analisar HGLG11 --html
```

O primeiro comando baixa os informes da CVM de todos os FIIs desde 2016
(~20 MB, com barra de progresso). O segundo abre o raio-x completo do fundo
no seu navegador. Pronto — está funcionando.

Todos os comandos disponíveis estão em [COMANDOS.txt](../COMANDOS.txt)
(troque `dist\scout.exe` por `uv run scout` se não tiver gerado o executável).

### Opcional: executável de duplo clique (sem terminal)

Rode `gerar_exe.bat` na raiz do projeto. Ele produz `dist\scout.exe`, que
funciona em qualquer Windows **sem Python instalado** — duplo clique abre um
modo interativo que aceita os mesmos comandos.

## Passo a passo (Linux / macOS)

```
git clone https://github.com/Ruamms/scout.git
cd scout
pip install uv        # ou: curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
uv run scout atualizar
uv run scout analisar HGLG11 --html
```

## Opcional: leitura de relatórios por IA (100% local)

A IA lê o relatório gerencial e os fatos relevantes do fundo citando os
trechos — nada sai da sua máquina e não há custo de token. Requisitos:
[Ollama](https://ollama.com) instalado e uma GPU com folga (o modelo padrão
ocupa ~9 GB).

```
winget install Ollama.Ollama        # Windows (Linux/macOS: veja ollama.com)
ollama pull qwen2.5:14b             # modelo padrão, o mais confiável
uv run scout ia HGLG11
```

GPU com menos de 10 GB de VRAM? Funciona, mas fica lento (parte do modelo
vai para a RAM). Alternativa mais leve: `ollama pull llama3.1:8b` e
`uv run scout ia HGLG11 --modelo llama3.1:8b`.

## Para desenvolvedores

```
uv run pytest         # 125 testes, todos com rede simulada (rodam offline)
```

Os testes das calculadoras executam o JavaScript real das páginas e pedem
Node.js — sem ele, são apenas pulados com aviso.

## Problemas comuns

**`python` ou `pip` não é reconhecido** — o Python foi instalado sem a opção
"Add to PATH". Reinstale marcando a caixa, ou use `py -m pip install uv`.

**`uv` não é reconhecido logo após o `pip install uv`** — feche e reabra o
Prompt de Comando (o PATH só atualiza em janelas novas). Se persistir, use
`python -m uv sync` e `python -m uv run scout ...`.

**O antivírus reclama do `scout.exe`** — falso positivo conhecido de
executáveis recém-gerados pelo PyInstaller. O código que gera o exe está
todo neste repositório, auditável.

**`scout atualizar` falha com erro de rede** — o portal de dados da CVM tem
janelas de manutenção (madrugadas e fins de semana). O programa tenta de
novo sozinho; se falhar, espere um pouco e rode outra vez.

**`scout ia` diz que o Ollama não está acessível** — abra o aplicativo
Ollama (ele precisa estar rodando; por padrão inicia com o sistema) e
confira o modelo com `ollama list`.

**A cotação parece velha** — fora do horário de pregão é normal (a página
mostra a data/hora do preço usado e avisa quando está defasado).
