# Especificação — Editor de Texto Simples para Linux

## 1. Objetivo

Desenvolver um editor de texto desktop simples para Linux, voltado exclusivamente para edição de texto puro.

O aplicativo deve ser rápido, minimalista e confiável, com foco na prevenção de perda de conteúdo. Ele não deve oferecer recursos de formatação, como negrito, itálico, títulos, cores, alinhamento ou inserção de imagens.

O principal diferencial do aplicativo será o salvamento automático e a recuperação do último documento aberto, inclusive quando o usuário fechar a janela sem salvar manualmente.

---

## 2. Plataforma e tecnologias

Utilizar:

- Python 3.12 ou superior.
- PySide6 para a interface gráfica.
- Qt Widgets.
- `QPlainTextEdit` como componente principal de edição.
- `QSettings` ou arquivos JSON para configurações.
- `pytest` para testes automatizados.

O aplicativo será inicialmente desenvolvido para Linux.

Não utilizar:

- Electron.
- Frameworks web.
- Banco de dados.
- Editor de texto rico.

---

## 3. Escopo da primeira versão

O aplicativo deve permitir:

- Criar documentos de texto.
- Abrir arquivos existentes.
- Salvar arquivos.
- Salvar arquivos com outro nome.
- Fechar o documento atual.
- Editar somente texto puro.
- Exibir números das linhas.
- Aumentar e diminuir o tamanho visual da fonte.
- Utilizar tema escuro.
- Localizar e substituir texto.
- Ativar ou desativar quebra automática de linha.
- Salvar automaticamente o conteúdo.
- Recuperar documentos não salvos.
- Reabrir automaticamente o último documento aberto.
- Abrir arquivos por argumento de linha de comando.

Inicialmente, o aplicativo trabalhará com somente um documento aberto por vez.

---

## 4. Interface principal

A janela principal deve possuir:

- Barra de menus.
- Área central de edição.
- Coluna lateral com números das linhas.
- Barra de status inferior.

### 4.1 Menu Arquivo

Criar as opções:

- Novo.
- Abrir.
- Salvar.
- Salvar como.
- Fechar documento.
- Sair.

### 4.2 Menu Editar

Criar as opções:

- Desfazer.
- Refazer.
- Recortar.
- Copiar.
- Colar.
- Selecionar tudo.
- Localizar.
- Substituir.

### 4.3 Menu Visualizar

Criar as opções:

- Aumentar fonte.
- Diminuir fonte.
- Restaurar tamanho da fonte.
- Ativar ou desativar quebra automática de linha.

---

## 5. Editor de texto

Utilizar preferencialmente `QPlainTextEdit`.

O editor deve:

- Trabalhar somente com texto puro.
- Preservar quebras de linha.
- Utilizar fonte monoespaçada.
- Permitir seleção de texto.
- Permitir copiar, recortar e colar.
- Permitir desfazer e refazer.
- Destacar discretamente a linha atual.
- Suportar arquivos grandes sem travamentos desnecessários.
- Não inserir números de linha no conteúdo.
- Não utilizar HTML ou formatação rica.

Fontes sugeridas:

- JetBrains Mono.
- DejaVu Sans Mono.
- Liberation Mono.
- Fonte monoespaçada padrão do sistema como fallback.

---

## 6. Numeração das linhas

A numeração deve aparecer em uma área fixa à esquerda do editor.

Requisitos:

- Iniciar no número 1.
- Atualizar automaticamente quando linhas forem adicionadas ou removidas.
- Acompanhar a rolagem vertical do editor.
- Ajustar a largura conforme a quantidade de linhas.
- Não fazer parte do conteúdo.
- Não ser selecionável.
- Não ser copiada.
- Não ser salva no arquivo.
- Destacar o número da linha atual.

Exemplo visual:

```text
1  Primeira linha
2  Segunda linha
3
4  Quarta linha
```

---

## 7. Tema escuro

O aplicativo deve iniciar sempre com tema escuro.

O tema deve ser aplicado em toda a interface:

- Janela principal.
- Editor.
- Menus.
- Diálogos.
- Barra de status.
- Barras de rolagem.
- Campo de pesquisa.
- Campo de substituição.

Características esperadas:

- Fundo escuro.
- Texto claro.
- Cursor visível.
- Seleção com contraste adequado.
- Linha atual com destaque discreto.
- Números das linhas com cor menos intensa.
- Número da linha atual com destaque.

Não é necessário implementar tema claro na primeira versão.

---

## 8. Controle de tamanho da fonte

O usuário deve conseguir aumentar e diminuir o tamanho visual da fonte.

Essa alteração deve afetar somente a visualização e nunca modificar o conteúdo do arquivo.

Atalhos:

- `Ctrl++`: aumentar a fonte.
- `Ctrl+-`: diminuir a fonte.
- `Ctrl+0`: restaurar o tamanho padrão.
- `Ctrl` + roda do mouse: alterar o tamanho da fonte, opcionalmente.

Configurações sugeridas:

- Tamanho padrão: 14 px.
- Tamanho mínimo: 8 px.
- Tamanho máximo: 40 px.
- Alteração de 1 px por ação.

O tamanho escolhido deve ser persistido e restaurado na próxima execução.

---

## 9. Tipos de documento

O editor deve trabalhar com dois estados principais.

### 9.1 Documento temporário

Documento criado pelo aplicativo que ainda não foi salvo em um arquivo escolhido pelo usuário.

Esse documento deve possuir:

- UUID próprio.
- Arquivo temporário persistente.
- Arquivo de metadados.
- Data de criação.
- Data da última alteração.
- Posição do cursor.
- Posição da rolagem.

O arquivo temporário não deve utilizar `/tmp` como armazenamento principal, pois o sistema pode limpar esse diretório.

Utilizar preferencialmente um caminho baseado em `QStandardPaths.AppDataLocation`, semelhante a:

```text
~/.local/share/simple-text-editor/recovery/
```

### 9.2 Documento associado a arquivo

Documento que foi:

- Aberto a partir do sistema de arquivos; ou
- Salvo pelo usuário por meio de "Salvar" ou "Salvar como".

Exemplo:

```text
/home/usuario/Documentos/anotacoes.txt
```

Mesmo documentos associados a arquivos devem possuir uma recuperação temporária enquanto estiverem sendo editados.

---

## 10. Salvamento automático

### 10.1 Regras gerais

Sempre que o conteúdo for alterado, o aplicativo deve salvar automaticamente uma recuperação.

Utilizar debounce para evitar escrita em disco a cada tecla.

Comportamento sugerido:

1. O usuário altera o texto.
2. Iniciar um temporizador de aproximadamente 500 milissegundos.
3. Se o usuário continuar digitando, reiniciar o temporizador.
4. Quando o usuário parar de digitar, salvar a recuperação.
5. Realizar também um salvamento periódico de segurança enquanto existirem alterações.

Intervalo periódico sugerido:

```text
5 segundos
```

### 10.2 Documento temporário

Quando o documento ainda não estiver associado a um arquivo definitivo:

- Salvar automaticamente no arquivo temporário.
- Atualizar os metadados.
- Mostrar na barra de status: `Salvo temporariamente`.
- Não abrir diálogo de salvamento automaticamente.
- Preservar o arquivo temporário ao fechar o aplicativo.
- Manter a recuperação sem prazo máximo.

### 10.3 Documento associado a arquivo

O salvamento automático deve, por padrão:

- Salvar uma recuperação temporária atualizada.
- Não depender apenas do arquivo original.
- Permitir recuperar alterações em caso de falha.

Pode também atualizar automaticamente o arquivo original, desde que isso seja implementado com segurança e seja uma decisão explícita da implementação.

A opção mais segura para a primeira versão é:

- Autosave sempre na recuperação temporária.
- `Ctrl+S` salva no arquivo original.
- Fechar pelo `X` preserva a recuperação.
- Reabrir o programa restaura a recuperação mais recente.

### 10.4 Escrita segura

Utilizar `QSaveFile` ou mecanismo equivalente.

Fluxo esperado:

1. Escrever em um arquivo auxiliar.
2. Garantir que a escrita foi concluída.
3. Fazer a substituição atômica.
4. Atualizar o estado somente após sucesso.

### 10.5 Erros de salvamento

Em caso de erro:

- Não perder o texto atual.
- Manter o conteúdo no editor.
- Tentar preservar uma recuperação alternativa.
- Mostrar `Erro ao salvar` na barra de status.
- Exibir uma mensagem discreta.
- Não bloquear a edição.
- Não apagar uma recuperação anterior válida.

---

## 11. Retenção dos arquivos temporários

Não deve existir prazo máximo de recuperação.

Os arquivos temporários:

- Não devem ser excluídos por idade.
- Não devem ser excluídos após 30 dias.
- Não devem ser excluídos após meses ou anos.
- Não devem ser excluídos durante atualizações do aplicativo.
- Não devem ser removidos ao fechar a janela pelo botão `X`.
- Não devem ser removidos ao selecionar "Sair".

Um arquivo temporário somente pode ser excluído quando:

1. O usuário escolher explicitamente `Não salvar` ao criar um novo documento.
2. O usuário escolher explicitamente `Não salvar` ao fechar o documento.
3. O documento for salvo definitivamente com sucesso e a recuperação não for mais necessária.
4. Existir no futuro uma ação explícita do usuário para excluir recuperações.

Não implementar limpeza automática por tempo.

---

## 12. Estrutura de recuperação

Exemplo:

```text
~/.local/share/simple-text-editor/
├── recovery/
│   ├── 8a1f2c4e.txt
│   └── 8a1f2c4e.json
└── session.json
```

Exemplo de metadados:

```json
{
  "id": "8a1f2c4e",
  "temporary": true,
  "original_path": null,
  "recovery_path": "/home/usuario/.local/share/simple-text-editor/recovery/8a1f2c4e.txt",
  "encoding": "UTF-8",
  "created_at": "2026-07-27T09:00:00-03:00",
  "updated_at": "2026-07-27T09:10:00-03:00",
  "cursor_position": 245,
  "scroll_position": 120
}
```

Todos os arquivos temporários devem utilizar UTF-8.

---

## 13. Restauração da última sessão

Ao abrir o programa:

1. Ler `session.json`.
2. Verificar qual era o último documento aberto.
3. Verificar se existe uma recuperação temporária.
4. Verificar se o arquivo original ainda existe.
5. Priorizar a recuperação quando ela possuir alterações mais recentes.
6. Abrir automaticamente o documento.
7. Restaurar a posição do cursor.
8. Restaurar a posição da rolagem.
9. Restaurar o tamanho da fonte.
10. Restaurar o estado da quebra automática de linha.

Se não existir documento recuperável, criar um documento temporário vazio.

A restauração deve ser automática e não deve perguntar ao usuário se deseja recuperar.

---

## 14. Comportamento ao fechar pelo botão X

Quando o usuário clicar no botão `X` da janela:

- Não perguntar se deseja salvar.
- Não abrir diálogo de confirmação.
- Salvar imediatamente o conteúdo na recuperação temporária.
- Atualizar os metadados da sessão.
- Preservar o arquivo temporário.
- Registrar o documento como o último documento aberto.
- Fechar o aplicativo.

Na próxima execução, o documento deve ser reaberto automaticamente.

Esse comportamento é obrigatório tanto para documentos temporários quanto para documentos associados a arquivos.

---

## 15. Ação Sair

A opção `Sair` e o atalho `Ctrl+Q` devem possuir o mesmo comportamento do botão `X`.

Ao sair:

- Não perguntar se deseja salvar.
- Salvar a recuperação.
- Atualizar a sessão.
- Preservar o documento temporário.
- Fechar o aplicativo.

A ação `Sair` não deve ser tratada como descarte do documento.

---

## 16. Ação Novo

Ao selecionar `Novo`, o aplicativo deve verificar se o documento atual possui conteúdo recuperável.

Quando houver conteúdo, exibir:

```text
Deseja salvar o documento atual?
```

Opções:

- Salvar.
- Não salvar.
- Cancelar.

### 16.1 Salvar

Se o usuário escolher `Salvar`:

- Se o documento já tiver caminho, salvar no arquivo atual.
- Se for temporário, abrir `Salvar como`.
- Somente criar o novo documento após o salvamento ser concluído.
- Se o salvamento falhar, manter o documento atual.
- Se o usuário cancelar o `Salvar como`, manter o documento atual.
- Após sucesso, remover a recuperação antiga quando ela não for mais necessária.
- Criar um novo documento temporário vazio.
- Gerar um novo UUID.

### 16.2 Não salvar

Se o usuário escolher `Não salvar`:

- Descartar o documento atual.
- Apagar o arquivo temporário.
- Apagar os metadados temporários.
- Remover a referência da sessão.
- Criar um novo documento temporário vazio.
- Gerar um novo UUID.

Essa ação é explícita e irreversível.

### 16.3 Cancelar

Se o usuário escolher `Cancelar`:

- Fechar o diálogo.
- Manter o documento atual.
- Não apagar arquivos.
- Não salvar.
- Não criar um novo documento.

### 16.4 Documento vazio

Se o documento estiver completamente vazio e nunca tiver recebido conteúdo:

- Criar diretamente um novo documento vazio.
- Não é necessário exibir a pergunta.

---

## 17. Ação Fechar documento

A opção `Fechar documento` deve fechar apenas o documento atual e manter o aplicativo aberto.

Antes de fechar, quando existir conteúdo recuperável, exibir:

```text
Deseja salvar o documento atual?
```

Opções:

- Salvar.
- Não salvar.
- Cancelar.

### 17.1 Salvar

- Salvar no arquivo atual, quando existir.
- Abrir `Salvar como`, quando o documento for temporário.
- Somente fechar após sucesso.
- Se o salvamento falhar, manter o documento aberto.
- Se o usuário cancelar o `Salvar como`, manter o documento aberto.
- Após fechar, criar um novo documento temporário vazio.

### 17.2 Não salvar

- Descartar o conteúdo atual.
- Excluir o arquivo temporário.
- Excluir os metadados da recuperação.
- Remover a referência da sessão.
- Criar um novo documento temporário vazio.

### 17.3 Cancelar

- Manter o documento aberto.
- Não alterar o conteúdo.
- Não excluir a recuperação.
- Não criar outro documento.

---

## 18. Matriz de comportamento

| Ação | Pergunta se deseja salvar | Preserva recuperação | Pode apagar recuperação |
|---|---:|---:|---:|
| Clicar no `X` | Não | Sim | Não |
| Menu `Sair` | Não | Sim | Não |
| `Ctrl+Q` | Não | Sim | Não |
| `Novo` | Sim | Depende da escolha | Sim, apenas em `Não salvar` |
| `Fechar documento` | Sim | Depende da escolha | Sim, apenas em `Não salvar` |
| Falha inesperada | Não | Sim | Não |
| Salvar definitivamente | Não | Até confirmar sucesso | Sim, após sucesso |

---

## 19. Ação Abrir

Ao selecionar `Abrir`:

1. Verificar o documento atual.
2. Aplicar o mesmo fluxo de confirmação da ação `Novo`.
3. Exibir o seletor de arquivos.
4. Permitir selecionar arquivos `.txt`.
5. Permitir selecionar todos os arquivos.
6. Abrir o arquivo.
7. Criar uma recuperação temporária associada.
8. Atualizar a sessão.
9. Registrar o caminho como último arquivo aberto.

Suportar inicialmente:

- UTF-8.
- UTF-8 com BOM.
- ISO-8859-1 como fallback.

Se a leitura falhar:

- Não substituir o documento atual.
- Informar o erro.
- Não sobrescrever o arquivo.
- Não perder a recuperação anterior.

---

## 20. Ação Salvar

Atalho:

```text
Ctrl+S
```

### Documento temporário

- Abrir o diálogo `Salvar como`.
- Sugerir `sem-titulo.txt`.
- Salvar em UTF-8.
- Associar o documento ao caminho escolhido.
- Atualizar o título da janela.
- Atualizar a sessão.
- Excluir a recuperação antiga apenas após confirmar sucesso.

### Documento associado a arquivo

- Salvar diretamente no arquivo atual.
- Utilizar escrita atômica.
- Atualizar a recuperação.
- Atualizar a sessão.
- Mostrar o estado `Salvo`.

---

## 21. Ação Salvar como

Atalho:

```text
Ctrl+Shift+S
```

Comportamento:

- Abrir o seletor de arquivos.
- Sugerir extensão `.txt`.
- Perguntar sobre substituição se o arquivo já existir.
- Salvar em UTF-8.
- Associar o documento ao novo caminho.
- Atualizar o título.
- Atualizar a sessão.
- Manter a recuperação até confirmar o salvamento.
- Excluir a recuperação antiga somente após sucesso.

---

## 22. Título da janela

Documento com arquivo:

```text
anotacoes.txt — Editor de Texto
```

Documento temporário:

```text
Sem título — Editor de Texto
```

Enquanto houver alteração ainda não salva nem mesmo na recuperação:

```text
● Sem título — Editor de Texto
```

O indicador deve desaparecer após o autosave.

---

## 23. Barra de status

Exibir:

- Linha atual.
- Coluna atual.
- Quantidade de caracteres.
- Estado do documento.
- Tamanho da fonte.
- Nome ou caminho do arquivo.

Estados possíveis:

- Salvo.
- Salvo temporariamente.
- Salvando.
- Alterado.
- Erro ao salvar.

Exemplo:

```text
Linha 15, Coluna 8 | 1.245 caracteres | Salvo temporariamente | Fonte 14 px
```

---

## 24. Localizar e substituir

### Localizar

Atalho:

```text
Ctrl+F
```

Criar uma barra de pesquisa dentro da janela com:

- Campo de texto.
- Próxima ocorrência.
- Ocorrência anterior.
- Diferenciar maiúsculas e minúsculas.
- Fechar com `Esc`.

### Substituir

Atalho:

```text
Ctrl+H
```

Adicionar:

- Texto procurado.
- Texto substituto.
- Substituir ocorrência atual.
- Substituir todas.

Não implementar expressões regulares na primeira versão.

---

## 25. Quebra automática de linha

Permitir ativar ou desativar a quebra visual automática.

Regras:

- Não modificar o conteúdo.
- Não inserir quebras no arquivo.
- Persistir a escolha.
- Quando estiver desativada, permitir rolagem horizontal.

---

## 26. Configurações persistentes

Salvar:

- Tamanho da fonte.
- Família da fonte.
- Tamanho da janela.
- Posição da janela.
- Estado maximizado.
- Quebra automática de linha.
- Último diretório de abertura.
- Último diretório de salvamento.
- Último documento aberto.
- Posição do cursor.
- Posição da rolagem.

Utilizar `QSettings` ou arquivo em:

```text
~/.config/simple-text-editor/
```

---

## 27. Atalhos

| Ação | Atalho |
|---|---|
| Novo | `Ctrl+N` |
| Abrir | `Ctrl+O` |
| Salvar | `Ctrl+S` |
| Salvar como | `Ctrl+Shift+S` |
| Sair | `Ctrl+Q` |
| Desfazer | `Ctrl+Z` |
| Refazer | `Ctrl+Shift+Z` |
| Recortar | `Ctrl+X` |
| Copiar | `Ctrl+C` |
| Colar | `Ctrl+V` |
| Selecionar tudo | `Ctrl+A` |
| Localizar | `Ctrl+F` |
| Substituir | `Ctrl+H` |
| Aumentar fonte | `Ctrl++` |
| Diminuir fonte | `Ctrl+-` |
| Restaurar fonte | `Ctrl+0` |

---

## 28. Estrutura sugerida do projeto

```text
simple-text-editor/
├── pyproject.toml
├── README.md
├── src/
│   └── simple_text_editor/
│       ├── __init__.py
│       ├── main.py
│       ├── application.py
│       ├── ui/
│       │   ├── main_window.py
│       │   ├── text_editor.py
│       │   ├── line_number_area.py
│       │   └── search_bar.py
│       ├── services/
│       │   ├── document_service.py
│       │   ├── autosave_service.py
│       │   ├── recovery_service.py
│       │   ├── session_service.py
│       │   └── settings_service.py
│       ├── models/
│       │   ├── document.py
│       │   └── session.py
│       └── resources/
│           └── dark.qss
└── tests/
    ├── test_autosave.py
    ├── test_recovery.py
    ├── test_session.py
    ├── test_document_service.py
    └── test_close_behavior.py
```

---

## 29. Modelo de documento

Criar uma classe semelhante a:

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

@dataclass
class Document:
    id: str
    content: str
    file_path: Path | None
    recovery_path: Path
    encoding: str
    is_temporary: bool
    is_dirty: bool
    last_saved_hash: str | None
    created_at: datetime
    updated_at: datetime
```

A interface não deve concentrar toda a lógica de arquivos.

Separar:

- Interface.
- Documento.
- Autosave.
- Recuperação.
- Sessão.
- Configurações.

---

## 30. Argumentos de linha de comando

Permitir:

```bash
simple-text-editor anotacoes.txt
```

Comportamento:

- Se o arquivo existir, abrir.
- Se não existir, criar documento associado ao caminho.
- Não criar o arquivo físico até o primeiro salvamento.
- Se nenhum caminho for informado, restaurar a sessão anterior.

---

## 31. Instância única

Preferencialmente permitir somente uma instância por usuário.

Se uma segunda instância for iniciada:

- Dar foco à instância existente.
- Se houver caminho de arquivo, encaminhá-lo para a instância aberta.
- Aplicar o fluxo de confirmação antes de trocar o documento.

Esse recurso pode ser implementado após a primeira versão funcional.

---

## 32. Logs

Salvar logs em:

```text
~/.local/state/simple-text-editor/app.log
```

Registrar:

- Inicialização.
- Encerramento.
- Arquivos abertos.
- Salvamentos.
- Autosaves.
- Recuperações.
- Erros de leitura.
- Erros de escrita.

Não registrar o conteúdo dos documentos.

Implementar rotação dos logs.

---

## 33. Empacotamento para Linux

Preparar:

1. Execução por ambiente virtual.
2. AppImage.
3. Pacote `.deb`.
4. Arquivo `.desktop`.

O arquivo `.desktop` deve:

- Exibir o aplicativo no menu.
- Permitir `Abrir com`.
- Permitir associação com `.txt`.
- Aceitar um caminho de arquivo como argumento.

Nome provisório:

```text
Simple Text Editor
```

O nome deve ser fácil de alterar.

---

## 34. Testes obrigatórios

### 34.1 Autosave temporário

1. Criar documento.
2. Digitar conteúdo.
3. Aguardar autosave.
4. Confirmar a criação do temporário.
5. Confirmar o conteúdo.

### 34.2 Fechar pelo X

1. Criar documento.
2. Digitar conteúdo.
3. Fechar pelo `X`.
4. Confirmar que não houve pergunta.
5. Abrir novamente.
6. Confirmar que o documento foi restaurado.

### 34.3 Sair pelo menu

1. Criar documento.
2. Digitar conteúdo.
3. Selecionar `Sair`.
4. Confirmar que não houve pergunta.
5. Abrir novamente.
6. Confirmar a recuperação.

### 34.4 Novo — Salvar

1. Criar documento com conteúdo.
2. Clicar em `Novo`.
3. Escolher `Salvar`.
4. Salvar o arquivo.
5. Confirmar criação de novo documento vazio.

### 34.5 Novo — Não salvar

1. Criar documento com conteúdo.
2. Clicar em `Novo`.
3. Escolher `Não salvar`.
4. Confirmar exclusão do temporário anterior.
5. Confirmar criação de novo documento vazio.

### 34.6 Novo — Cancelar

1. Criar documento.
2. Clicar em `Novo`.
3. Escolher `Cancelar`.
4. Confirmar que nada mudou.

### 34.7 Fechar documento — Não salvar

1. Criar documento.
2. Selecionar `Fechar documento`.
3. Escolher `Não salvar`.
4. Confirmar exclusão da recuperação.
5. Confirmar abertura de documento vazio.

### 34.8 Cancelamento do Salvar como

1. Criar documento temporário.
2. Clicar em `Novo`.
3. Escolher `Salvar`.
4. Cancelar o diálogo.
5. Confirmar que o documento atual continua aberto.

### 34.9 Recuperação sem prazo

1. Criar recuperação com data antiga.
2. Iniciar o aplicativo.
3. Confirmar que a recuperação continua disponível.
4. Confirmar que nenhum processo automático a excluiu.

### 34.10 Numeração das linhas

1. Inserir linhas.
2. Remover linhas.
3. Confirmar atualização da numeração.
4. Confirmar que números não estão no arquivo salvo.

### 34.11 Erro de escrita

1. Simular falta de permissão.
2. Alterar o documento.
3. Tentar salvar.
4. Confirmar preservação da recuperação.
5. Confirmar que o conteúdo continua no editor.

---

## 35. Critérios de aceite

O projeto será considerado concluído quando:

- Funcionar em Linux.
- Utilizar Python e PySide6.
- Editar apenas texto puro.
- Possuir tema escuro.
- Exibir números das linhas.
- Permitir aumentar e diminuir a fonte.
- Restaurar o tamanho da fonte.
- Criar recuperação automática persistente.
- Não utilizar `/tmp` como único armazenamento.
- Não existir prazo máximo de recuperação.
- Fechar pelo `X` sem perguntar.
- Preservar o temporário ao fechar pelo `X`.
- Restaurar o último documento automaticamente.
- `Sair` possuir o mesmo comportamento do `X`.
- `Novo` perguntar se deseja salvar.
- `Fechar documento` perguntar se deseja salvar.
- Escolher `Não salvar` excluir o temporário.
- Escolher `Cancelar` preservar o documento.
- Cancelar `Salvar como` impedir a troca do documento.
- Erros de gravação não causarem perda de texto.
- Números das linhas não fazerem parte do arquivo.
- Arquivos serem salvos em UTF-8 por padrão.
- A posição do cursor ser restaurada.
- A posição da rolagem ser restaurada.
- O aplicativo poder ser iniciado pelo menu do Linux.

---

## 36. Regras obrigatórias para a implementação

- Não implementar formatação rica.
- Não utilizar banco de dados.
- Não apagar recuperações por idade.
- Não perguntar ao fechar pelo `X`.
- Não perguntar ao selecionar `Sair`.
- Sempre preservar o documento ao encerrar o aplicativo.
- Perguntar ao usar `Novo`.
- Perguntar ao usar `Fechar documento`.
- Excluir o temporário somente após escolha explícita de `Não salvar`.
- Não trocar de documento caso `Salvar como` seja cancelado.
- Não excluir recuperação antes de confirmar um salvamento definitivo.
- Não registrar conteúdo nos logs.
- Priorizar a prevenção de perda de conteúdo.
- Utilizar escrita atômica sempre que possível.
- Separar a interface da lógica de persistência.

---

## 37. Ordem sugerida de implementação

### Etapa 1 — Editor básico

- Janela principal.
- Tema escuro.
- Editor de texto puro.
- Numeração das linhas.
- Barra de status.
- Controle da fonte.

### Etapa 2 — Arquivos

- Novo.
- Abrir.
- Salvar.
- Salvar como.
- Fechar documento.
- Fluxos de confirmação.

### Etapa 3 — Autosave

- Documento temporário.
- UUID.
- Debounce.
- Escrita atômica.
- Indicador de status.

### Etapa 4 — Sessão

- `session.json`.
- Último documento.
- Restauração automática.
- Cursor.
- Rolagem.
- Fechamento pelo `X`.

### Etapa 5 — Recursos adicionais

- Localizar.
- Substituir.
- Quebra automática.
- Argumentos de linha de comando.
- Instância única.
- Logs.

### Etapa 6 — Qualidade e distribuição

- Testes automatizados.
- AppImage.
- Pacote `.deb`.
- Arquivo `.desktop`.
- Associação com arquivos `.txt`.
