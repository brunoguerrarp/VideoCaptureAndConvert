# VideoScreenCapture

Captura frames de mudança de tela a partir de um vídeo MP4 ou diretamente da tela em tempo real, salvando as imagens em um arquivo ZIP.

---

## Instalação

Baixe o `VideoScreenCapture.exe` e execute diretamente — sem instalação necessária.

---

## Modos de uso

### Aba "Arquivo de Vídeo"

Processa um arquivo `.mp4` já gravado e extrai os frames onde houve mudança de tela.

1. Arraste o arquivo `.mp4` para a área indicada, ou clique para selecionar.
2. Ajuste as configurações de detecção (veja abaixo).
3. Defina a pasta e o nome do arquivo de saída.
4. Clique em **Processar Vídeo**.
5. Ao terminar, o ZIP com os frames capturados é salvo na pasta escolhida.

---

### Aba "Captura ao Vivo"

Captura a tela em tempo real enquanto você trabalha.

#### Fontes disponíveis

| Fonte | Descrição |
|---|---|
| **Monitor** | Captura um monitor inteiro. Selecione qual na lista. |
| **Janela** | Captura uma janela específica aberta no momento. Selecione na lista. |
| **Região Personalizada** | Você desenha a área da tela a capturar. |

#### Como usar Região Personalizada

1. Selecione **Região Personalizada**.
2. Clique em **Selecionar Região na Tela** — a janela minimiza e aparece um overlay escurecido.
3. Clique e arraste para desenhar a área desejada.
4. Solte o mouse para confirmar. Pressione **ESC** para cancelar.

#### Iniciar e parar a captura

- Clique em **Iniciar Captura** para começar.
  - Em modo **Região Personalizada**, a janela minimiza automaticamente para não aparecer na gravação.
- Clique em **Parar** para encerrar, ou use o atalho de teclado global **Ctrl + Shift + S** — funciona mesmo com a janela minimizada.
- Ao parar, a janela restaura automaticamente e o ZIP é salvo.

---

## Configurações de detecção

| Parâmetro | Descrição | Padrão |
|---|---|---|
| **Sensibilidade (threshold)** | Diferença mínima entre frames para considerar mudança. Menor = mais sensível. | 5.0 |
| **Intervalo mínimo (seg)** | Tempo mínimo entre duas capturas consecutivas. | 0.5 s |
| **Formato das imagens** | PNG (sem perda) ou JPG (menor tamanho). | PNG |
| **Verificações por segundo** | Frequência de análise da tela (apenas captura ao vivo). Maior = mais preciso, mais CPU. | 5 |

---

## Arquivo de saída

Os frames são salvos em um arquivo `.zip` contendo imagens nomeadas sequencialmente:

```
screens.zip
├── Screen0001.png
├── Screen0002.png
└── ...
```

---

## Atalhos

| Atalho | Ação |
|---|---|
| **Ctrl + Shift + S** | Para a captura ao vivo (global, funciona com janela minimizada) |
| **ESC** | Cancela a seleção de região |

---

*Powered by Guerra*
