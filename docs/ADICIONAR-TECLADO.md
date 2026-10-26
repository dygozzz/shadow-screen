# Como adicionar um teclado novo (ex.: EPOMAKER RT85)

Este guia mostra como fazer o Shadow Screen funcionar com outro teclado EPOMAKER que tenha
tela. O Shadow-S foi adicionado exatamente assim.

A ideia geral: o programa oficial da EPOMAKER sabe "conversar" com a tela do teclado. Nós
**gravamos essa conversa** enquanto ele envia um GIF de teste com cores conhecidas, descobrimos
o formato e escrevemos um arquivo Python que repete a mesma conversa.

> **Atalho:** se você usa o [Claude Code](https://claude.com/claude-code), abra a pasta do
> projeto nele e peça: *"siga o docs/ADICIONAR-TECLADO.md para adicionar o RT85"*. Ele consegue
> rodar os passos, ler a gravação e escrever o código com você. Mesmo assim, leia o guia para
> saber o que está acontecendo.

---

## 0. O que você precisa

- O teclado (RT85) ligado **por cabo USB**
- Windows 10/11
- O **programa oficial** que troca a imagem da tela (para o RT85, é o *EPOMAKER 3.0*, no site da
  EPOMAKER)
- **Python 3.12**: `winget install Python.Python.3.12`
- **Git**: `winget install Git.Git`
- Uma conta no GitHub (para mandar a mudança de volta)

## 1. Baixar o projeto

1. No GitHub, abra `https://github.com/dygozzz/shadow-screen` e clique em **Fork**. Isso cria
   uma cópia do projeto na sua conta.
2. No PowerShell:
   ```powershell
   git clone https://github.com/SEU-USUARIO/shadow-screen.git
   cd shadow-screen
   python -m pip install --user hidapi pywebview frida-tools pillow
   ```

## 2. Descobrir os dados do teclado

Com o teclado plugado:

```powershell
python tools\list_devices.py
```

Vai aparecer algo assim (exemplo do Shadow-S):

```
320F:5055  RDR EPOMAKER Shadow-S
    interface 0   usage_page 0x0001  usage 0x06
    interface 1   usage_page 0xFF60  usage 0x61   <-- vendor-defined
    interface 2   usage_page 0x0001  usage 0x06
    interface 2   usage_page 0xFFEF  usage 0x00   <-- vendor-defined
    interface 3   usage_page 0xFF1C  usage 0x92   <-- vendor-defined
```

Se o seu teclado não aparecer, rode `python tools\list_devices.py --all` e procure pelo nome
dele.

Anote:
- **VID:PID**, o par antes do espaço (`320F:5055` no exemplo);
- as linhas marcadas **vendor-defined**: uma delas é o canal da tela. A `0xFF60` costuma ser a do
  VIA, então a tela normalmente é a outra.

Descubra também a **resolução da tela**: no programa oficial (às vezes ele mostra ou recorta a
imagem nesse tamanho), no manual ou na página do produto.

## 3. Criar o GIF de teste

Troque `LARGURA ALTURA` pela resolução da tela:

```powershell
python tools\capture\make_test_gif.py teste.gif LARGURA ALTURA
```

Ele tem 4 frames: vermelho, verde, azul e um com metade branca e metade preta, mais um
quadradinho vermelho no canto superior esquerdo. Com cores conhecidas fica fácil achar os pixels
na gravação.

## 4. Gravar o programa oficial

Feche o VIA e qualquer outro programa do teclado. Depois siga **um** dos caminhos abaixo.

### 4a. Se o programa oficial é um app de PC (.exe)

Abra o PowerShell **como administrador**, porque muitos desses programas pedem admin, e rode
apontando para o .exe do programa oficial:

```powershell
cd caminho\do\shadow-screen
python tools\capture\capture.py "C:\Program Files\...\EPOMAKER.exe" rt85-log.jsonl
```

O programa abre já sendo gravado. **Feche antes qualquer cópia dele**, inclusive pelo ícone perto
do relógio, e **não abra o programa por outro jeito**. Nele:
1. importe o `teste.gif`;
2. **anote o intervalo/velocidade** que estiver configurado (ex.: 500 ms);
3. envie para o teclado;
4. **confira que o GIF apareceu certinho na tela do teclado**;
5. feche o programa oficial. A gravação para sozinha.

Durante a gravação, o terminal mostra `capturing: N packets sent to devices so far`. Se essa
linha nunca aparecer, nada está sendo gravado.

Se aparecer `unable to spawn ... 0x000002e4`, é porque o terminal não está como administrador.

**Se não gravar nada** (programas que ficam na bandeja ou que se reabrem sozinhos): abra o
programa oficial **normalmente**, deixe ele aberto e grave conectando na cópia que já está
rodando. Troque o nome pelo nome do .exe dele:

```powershell
python tools\capture\capture.py --attach "NomeDoPrograma.exe" rt85-log.jsonl
```

Quando aparecer `attached to N process(es)`, faça o envio do GIF. No fim, feche o programa ou
crie um arquivo chamado `STOP` na pasta para encerrar a gravação.

### 4b. Se o programa oficial é um site (abre no Chrome)

1. Abra o site oficial no Chrome e aperte **F12**, depois a aba **Console**.
2. **Antes de conectar o teclado no site**, cole todo o conteúdo de
   `tools\capture\webhid_capture.js` no console e aperte Enter.
3. Conecte o teclado pelo site, importe o `teste.gif`, anote o intervalo e envie.
4. No console, rode `copy(JSON.stringify(window.__hidlog))`. Isso copia a gravação.
5. Cole num arquivo `rt85-log.json` na pasta do projeto.

## 5. Ler a gravação

```powershell
python tools\capture\summarize.py rt85-log.jsonl
```

A saída mostra a conversa resumida: os comandos curtos e os blocos grandes de dados (`x4682`
significa 4682 pacotes parecidos seguidos, que geralmente são os pixels). No fim, ele procura as
cores do GIF de teste:

| Se aparecer... | Os pixels estão em... |
|---|---|
| `f800`, `07e0`, `001f` | RGB565 big-endian (igual ao Shadow-S) |
| `00f8`, `e007`, `1f00` | RGB565 little-endian |
| `ff0000`, `00ff00`, `0000ff` | RGB888 |
| nada | comprimido ou num formato próprio: dá mais trabalho, veja a dica abaixo |

O que descobrir, olhando a gravação:
1. **Formato do pacote:** tamanho (64 bytes?), report ID (primeiro byte), se tem checksum (no
   Shadow-S, os bytes 1 e 2 são a soma dos demais), onde fica o comando e o endereço.
2. **Sequência:** quais comandos vêm antes dos pixels (início, configuração, apagar memória) e
   depois (fim).
3. **Configuração:** procure o número de frames (4) e o intervalo que você anotou (500 = `01f4`,
   que em little-endian aparece como `f4 01`).
4. **Pixels:** em que ordem os frames vão, se cada frame é preenchido até um tamanho fixo (no
   Shadow-S, 64 KB) e quantos bytes de pixel vão por pacote.
5. **Respostas:** o que o teclado responde a cada pacote (no Shadow-S, ele devolve o mesmo
   cabeçalho, como confirmação).

Use o [PROTOCOL.md](../PROTOCOL.md) do Shadow-S como exemplo do que procurar.

**Dica:** se os pixels estiverem comprimidos, veja o projeto
[rt82display](https://github.com/guysoft/rt82display), que documentou um formato comprimido de
outro teclado EPOMAKER (RT82). Pode ser o mesmo do RT85.

## 6. Escrever o modelo

1. Copie `launcher\models\_template.py` para `launcher\models\rt85.py`.
2. Preencha `ID`, `NAME`, `VID`, `PID`, `USAGE_PAGE`, `WIDTH`, `HEIGHT`, `MAX_FRAMES` e `PREVIEW`.
   Em `MAX_FRAMES`, comece com o máximo que o programa oficial deixa, e nunca mais que isso.
3. Escreva `upload()` para enviar **exatamente os mesmos pacotes** que o programa oficial
   mandou: mesma ordem, mesmos tamanhos e as mesmas pausas. O `launcher\models\shadow_s.py` é um
   exemplo completo.
4. Registre o modelo em `launcher\models\__init__.py`:
   ```python
   from . import rt85, shadow_s

   MODELS = [shadow_s, rt85]
   ```

O app se adapta sozinho à resolução, ao limite de frames e ao nome do modelo.

## 7. Conferir antes de mandar para o teclado

Antes de enviar qualquer coisa de verdade, **compare os pacotes que o seu código gera com os da
gravação**, usando o `teste.gif` e o mesmo intervalo. Eles devem ser idênticos, com exceção da
data e hora, que mudam, e do enchimento entre frames.

Uma forma simples: faça uma versão de `upload()` que, em vez de enviar, guarda os pacotes numa
lista, e compare com os `write` da gravação. Foi assim que o Shadow-S foi validado: 4682 pacotes
iguais antes do primeiro envio real.

## 8. Testar no teclado

1. Feche o programa oficial e o VIA.
2. Abra o Shadow Screen: `pythonw launcher\shadow_screen.py`, ou rode `Instalar atalhos.cmd` e
   use o atalho.
3. O app deve mostrar **"EPOMAKER RT85 conectado"**.
4. Envie primeiro o `teste.gif`. Só depois teste GIFs de verdade.

Se algo der errado: desconecte e reconecte o teclado, e envie um GIF pelo programa oficial para
voltar ao normal.

## 9. Mandar para o projeto

1. Anote o protocolo numa seção nova do `PROTOCOL.md`, como foi feito para o Shadow-S.
2. **Não** envie o arquivo de gravação (`*.jsonl`/`*.json`): ele é grande e o `.gitignore` já
   ignora `*.jsonl`.
3. ```powershell
   git checkout -b rt85
   git add launcher\models PROTOCOL.md
   git commit -m "Add EPOMAKER RT85 support"
   git push -u origin rt85
   ```
4. No GitHub, abra um **Pull Request** do seu fork para `dygozzz/shadow-screen`.

## Segurança

- O app **nunca** envia nada para um teclado que não esteja em `MODELS`. Enquanto o RT85 não
  estiver registrado, ele só aparece como "não compatível".
- Sempre copie o que o programa oficial faz. Não invente comandos nem passe dos limites que ele
  usa (número de frames, tamanho), porque dá para sobrescrever outras partes da memória do
  teclado.
- Comece com GIFs pequenos.
