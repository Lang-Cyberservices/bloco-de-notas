# Bloco de Notas

Editor de texto simples para Linux, feito em Python 3.12 com PySide6.
Só texto puro — nada de negrito, títulos, cores ou imagens.

O diferencial é a **prevenção de perda de conteúdo**: tudo o que você digita vai
para uma recuperação automática em disco, e o último documento reabre sozinho na
execução seguinte. Fechar a janela no `X` nunca pergunta nada e nunca perde nada.

## Instalação

### AppImage (qualquer distribuição)

Baixe o `.AppImage` de `dist/`, dê permissão de execução e rode:

```bash
chmod +x Bloco_de_Notas-0.1.0-x86_64.AppImage && ./Bloco_de_Notas-0.1.0-x86_64.AppImage
```

Funciona em qualquer distribuição com **glibc 2.31 ou mais nova**: Fedora 33+,
Ubuntu 20.04+, Debian 11+, Mint 20+, openSUSE 15.3+, RHEL 9. Não precisa instalar
Python nem Qt — está tudo dentro do arquivo.

**Se o duplo clique não fizer nada**, quase sempre é a `libfuse2`, que Fedora e
distros recentes não instalam por padrão. Três saídas, da mais simples à mais direta:

```bash
./Bloco_de_Notas-0.1.0-x86_64.AppImage --appimage-extract-and-run
```

```bash
sudo dnf install fuse-libs      # Fedora / RHEL
sudo apt install libfuse2       # Debian / Ubuntu / Mint
```

Ou use o `.tar.gz`, que não depende de FUSE nenhum:

```bash
tar -xzf bloco-de-notas-0.1.0-x86_64.tar.gz && ./bloco-de-notas-0.1.0-x86_64/bloco-de-notas
```

### A partir do código

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
```

## Uso

```bash
.venv/bin/python -m bloco_de_notas
```

Abrindo um arquivo direto:

```bash
.venv/bin/python -m bloco_de_notas ~/Documentos/anotacoes.txt
```

Se o arquivo não existir, o documento é associado ao caminho e o arquivo só é
criado no primeiro `Ctrl+S`.

### Entrada no menu do Linux

```bash
./scripts/instalar-desktop.sh
```

Depois disso o aplicativo aparece no menu e em "Abrir com" para arquivos `.txt`.

## Como o conteúdo é protegido

| Situação | O que acontece |
|---|---|
| Você para de digitar por 0,5 s | O texto vai para a recuperação |
| Você digita sem parar | Uma gravação de segurança a cada 5 s |
| Você fecha no `X` ou usa `Ctrl+Q` | Salva a recuperação e sai, sem perguntar |
| Você reabre o aplicativo | O último documento volta com cursor e rolagem |
| `Ctrl+S` falha (disco cheio, sem permissão) | O texto continua no editor e a recuperação anterior continua válida |
| `Novo` ou `Fechar documento` | Aí sim pergunta: Salvar / Não salvar / Cancelar |

O autosave **nunca grava no seu arquivo**: só `Ctrl+S` faz isso. Assim o arquivo
em disco nunca muda sem você mandar, e mesmo assim nada se perde.

**As recuperações não expiram.** Não há limpeza por idade, nem depois de meses
ou anos. Uma recuperação só é apagada quando você escolhe explicitamente
"Não salvar", ou depois que o documento foi salvo em definitivo.

## Onde ficam os arquivos

```text
~/.local/share/bloco-de-notas/
├── recovery/
│   ├── 8a1f2c4e.txt      conteúdo
│   └── 8a1f2c4e.json     metadados (cursor, rolagem, datas)
└── session.json          último documento aberto

~/.config/bloco-de-notas/settings.ini    fonte, janela, quebra de linha
~/.local/state/bloco-de-notas/app.log    logs (nunca o conteúdo dos documentos)
```

## Atalhos

| Ação | Atalho | | Ação | Atalho |
|---|---|---|---|---|
| Novo | `Ctrl+N` | | Localizar | `Ctrl+F` |
| Abrir | `Ctrl+O` | | Substituir | `Ctrl+H` |
| Salvar | `Ctrl+S` | | Aumentar fonte | `Ctrl++` |
| Salvar como | `Ctrl+Shift+S` | | Diminuir fonte | `Ctrl+-` |
| Fechar documento | `Ctrl+W` | | Restaurar fonte | `Ctrl+0` |
| Sair | `Ctrl+Q` | | Desfazer / Refazer | `Ctrl+Z` / `Ctrl+Shift+Z` |

`Ctrl` + roda do mouse também muda o tamanho da fonte (8 a 40 px).

## Testes

```bash
.venv/bin/python -m pytest
```

A suíte cobre os onze casos obrigatórios da especificação, incluindo os que
protegem contra perda de conteúdo: erro de escrita, cancelamento do "Salvar
como", fechamento pelo `X` e recuperação com anos de idade.

## Gerando o AppImage

```bash
./scripts/build-appimage.sh
```

A construção roda dentro de um container **Debian 11** — não é capricho: a glibc da
máquina que compila vira o piso de compatibilidade do binário. Construir num sistema
recente produziria um AppImage que só abre em distribuições de 2024 em diante.

Pelo mesmo motivo o PySide6 fica fixado em **6.9.3**: da 6.10 em diante os wheels
passaram a exigir glibc 2.34, o que sozinho excluiria Ubuntu 22.04 e Fedora 35.

Para conferir o resultado nas distribuições alvo antes de distribuir:

```bash
./scripts/appimage/verificar-distros.sh
```

Isso roda o artefato em containers Fedora, Debian e Ubuntu, exigindo que **nenhuma
biblioteca fique sem resolver** e que o ciclo digitar → autosave → fechar → reabrir →
salvar funcione em cada uma.

## Estrutura

```text
src/bloco_de_notas/
├── main.py            argumentos, logs, instância única
├── application.py     montagem: caminhos → serviços → janela
├── paths.py           onde os dados moram (injetável, para os testes)
├── models/            Document e SessionState
├── services/          escrita atômica, recuperação, sessão, autosave, diálogos
└── ui/                janela, editor, coluna de números, busca, tema
```

A interface não lê nem grava arquivos: ela dispara ações no `DocumentService` e
reflete os sinais dele. Os diálogos ficam atrás de um `Protocol`, o que permite
testar as regras de "Salvar / Não salvar / Cancelar" sem janelas modais.
