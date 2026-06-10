# Blueprint — Importação de DUIMP para o Omie (Nota de Entrada)

> Documento de estruturação da ideia. Define arquitetura, contratos, mapeamento de campos e decisões pendentes **antes** de construir o fluxo no n8n.
> Status: rascunho para revisão. Itens marcados com **[A CONFIRMAR]** dependem de definição sua.

---

## 1. Objetivo

Transformar o **Extrato da DUIMP** (PDF) na **Nota de Entrada** do Omie, criada via API (`IncluirNotaEnt`, JSON). A nota de entrada é a forma contábil de registrar a importação.

O XML da NF-e de entrada que vocês geram hoje passa a servir como **gabarito de conferência** (o resultado esperado), não como artefato a ser gerado.

---

## 2. Arquitetura geral

```
┌─────────────────────────┐     POST 1 (JSON + PDF base64)     ┌──────────────────────────┐
│  FRONT — Streamlit       │ ─────────────────────────────────► │  BACK — n8n              │
│  (só apresentação)       │                                    │  (toda a lógica)         │
│                          │ �„──── resposta: itens + candidatos ─│                          │
│  - upload da DUIMP       │                                    │  - decodifica base64     │
│  - mostra itens          │                                    │  - extrai dados da DUIMP │
│  - seletor por item      │     POST 2 (decisão do usuário)    │  - valida NCM            │
│  - você escolhe          │ ─────────────────────────────────► │  - resolve fornecedor    │
│  - clica enviar          │                                    │  - cria produto (Upsert) │
│                          │ �„──── resposta: resultado import ───│  - IncluirNotaEnt        │
└─────────────────────────┘                                    └────────────┬─────────────┘
                                                                             │ API Omie
                                                                             ▼
                                                                   ┌──────────────────┐
                                                                   │  OMIE            │
                                                                   │  Nota de Entrada │
                                                                   └──────────────────┘
```

**Princípios fechados:**

- **Separação front/back:** o Streamlit só apresenta e coleta escolhas. Não lê PDF, não consulta o Omie, não valida nada.
- **Transporte:** o front envia o PDF em **base64 dentro de JSON** (mesmo `montar_payload` que já existe). Nada de PDF cru / multipart.
- **Dois passos manuais (sem loop automático):** os dois POSTs são disparados por você na tela. O back nunca "reconfirma" sozinho.
- **Toda regra mora no n8n.**

---

## 3. Fluxo detalhado

### Passo 1 — Upload e validação
1. Você sobe a DUIMP (PDF) no Streamlit e clica em enviar.
2. Front faz **POST 1** com o PDF em base64.
3. n8n: decodifica → extrai os itens da DUIMP → para cada item filtra produtos no Omie por **NCM** (`ListarProdutos`/`ListarProdutosResumido`).
4. n8n responde com a lista de itens + candidatos por NCM.

### Passo 2 — Seleção manual e importação
5. A tela mostra, **para cada item**, um seletor com os candidatos encontrados + sempre a opção **"➕ Criar novo produto"**.
6. Você escolhe item a item (PRD existente ou criar novo) e confere valores/fornecedor.
7. Front faz **POST 2** com tudo já decidido.
8. n8n: para cada item marcado como "novo", chama `UpsertProduto` (com o NCM da DUIMP); monta o JSON da nota; chama `IncluirNotaEnt`.
9. n8n responde com o resultado (sucesso / código da nota / erros).

---

## 4. Contrato dos webhooks

### POST 1 — `/duimp/extrair` (front → n8n)
Reaproveita o `montar_payload` atual, trocando o tipo de arquivo:

```json
{
  "email": "willian.silva@sillion.com.br",
  "empresa": "Sillion",
  "filename": "EXTRATO-DUIMP-26BR0000407051-9.pdf",
  "file_base64": "JVBERi0xLjQ...",
  "mime_type": "application/pdf",
  "data_lancamento": "2026-06-09"
}
```

**Resposta do n8n (itens + candidatos):**
```json
{
  "duimp": "26BR0000407051-9",
  "fornecedor": { "encontrado": true, "nCodCli": 0000, "nome": "MOKO TECHNOLOGY LTD" },
  "itens": [
    {
      "item_duimp": 1,
      "descricao_duimp": "PLACA DE CIRCUITO IMPRESSO DO DISPLAY DO STD156",
      "ncm": "85299040",
      "qtde": 2000,
      "valor_unit_sugerido": 38.65,
      "candidatos": [
        { "nCodProd": 0000, "codigo": "PRD000024", "descricao": "PLACA ELETRONICA PARA EQUIPAMENTO STD156" },
        { "nCodProd": 0000, "codigo": "PRD000029", "descricao": "PLACA ELETRONICA DSP STD 156 BOARD LCD" }
      ]
    }
  ]
}
```

### POST 2 — `/duimp/importar` (front → n8n)
```json
{
  "duimp": "26BR0000407051-9",
  "data_lancamento": "2026-06-09",
  "cabec": { "nCodCli": 0000, "cCodCateg": "[A CONFIRMAR]" },
  "itens": [
    {
      "item_duimp": 1,
      "acao": "usar_existente",          // ou "criar_novo"
      "nCodProd": 0000,                   // se usar_existente
      "codigo_novo": null,                // se criar_novo → próximo PRD
      "ncm": "85299040",
      "qtde": 2000,
      "valor_unit": 38.65,
      "cfop": "3556"
    }
  ]
}
```

---

## 5. Mapeamento campo-a-campo: DUIMP → `IncluirNotaEnt`

### Cabeçalho (`cabec` + `infAdic`)

| Campo Omie | Origem | Observação |
|---|---|---|
| `cCodIntNotaEnt` | Gerado a partir do nº da DUIMP | Chave de integração para não duplicar nota |
| `nCodCli` | `ListarClientesResumido` (filtro por CNPJ/razão do exportador) | Fornecedor = MOKO TECHNOLOGY |
| `dPrevisao` | `data_lancamento` do front | |
| `cCodCateg` | **[A CONFIRMAR]** | Categoria contábil (ex.: "2.01.03") |
| `nCodCC` | **[A CONFIRMAR]** | Conta corrente, se gerar financeiro |

### Itens (`produtos[]`) — 1 item da DUIMP = 1 item da nota

| Campo Omie | Origem na DUIMP | Observação |
|---|---|---|
| `nCodProd` | Resolvido por NCM (seleção) ou retorno do `UpsertProduto` | |
| `cCFOP` | `3556` (do XML modelo) | Compra do exterior p/ uso/consumo — **[A CONFIRMAR]** se varia por item |
| `nQtde` | "Quantidade na unidade comercializada" | Item 1 = 2000 |
| `nValUnit` | Valor contábil ÷ qtde (ver §7) | **[A CONFIRMAR]** regra de composição |
| `cNCM` | NCM da DUIMP | Item 1 = 85299040 |
| `ICMS` / `IPI` / `PIS` / `COFINS` | Tributos por item da DUIMP, ou defaults do cadastro do produto | Ver §6 |
| `IBS_CBS` (`cCstIbsCbs`, `cClassTrib`) | `class_trib` = 000001 (da DUIMP) | Reforma tributária |
| `codigo_local_estoque` | **[A CONFIRMAR]** | Local de estoque no Omie |

---

## 6. Regra de produto (NCM + criar novo)

- O `codigo` do produto **é seu, editável** (não é gerado pelo Omie). O ID interno gerado é o `nCodProd` (inteiro).
- Padrão de vocês: **`PRD` + 6 dígitos** (catálogo atual vai de `PRD000002` a `PRD000032`).
- Resolução por item:

```
filtra produtos por NCM
  ├─ achou 1 ou mais  → mostra na tela p/ você escolher  + sempre "➕ criar novo"
  └─ achou nenhum     → mostra só "➕ criar novo"
```

- **Criar novo:** o n8n lê o maior `PRD` existente (`ListarProdutos`) e incrementa (`PRD000033`...), depois chama `UpsertProduto` com o NCM da DUIMP. `UpsertProduto` é idempotente pela chave `codigo`, então reprocessar não duplica.
- **Atenção (já mapeado nos dados):** nesta DUIMP, todo NCM retorna 2 candidatos ou nenhum — por isso a seleção manual é essencial:

| Item | NCM | Candidatos no Omie |
|---|---|---|
| 1 (Placa DSP) | 85299040 | PRD000024, PRD000029 |
| 2–4 (Gabinete) | 85389090 | PRD000023, PRD000031 |
| 5 (Membrana) | 83100000 | PRD000006, PRD000026 |
| 6 (Display LCD) | 85312000 | nenhum → criar novo |

---

## 7. Composição de valores **[A CONFIRMAR]**

No XML modelo, o valor por item **não é o FOB da DUIMP** — é o **valor contábil** (valor aduaneiro + tributos rateados).

Exemplo item 1: `nValUnit` = R$ 38,65 → `vProd` = 2000 × 38,65 = **R$ 77.300,00**
(DUIMP: valor aduaneiro do item = R$ 49.603,32; base ICMS = R$ 76.278,15).

Totais que precisam fechar:

| Componente | Valor (R$) |
|---|---|
| Valor aduaneiro | 142.523,09 |
| II | 18.320,12 |
| IPI | 11.325,04 |
| PIS | 2.992,98 |
| COFINS | 13.753,48 |
| ICMS | 41.875,72 |
| Outras despesas / Siscomex | ~3.090,85 |
| **Total da nota (vNF)** | **233.625,94** |

**Pendência:** confirmar a fórmula exata do `nValUnit` por item (rateio + arredondamento para preço unitário "redondo"), porque o preço unitário do XML não é exatamente a base de ICMS dividida pela quantidade.

---

## 8. Adaptação do front (FrontWebDuimpOmie)

Reaproveita o esqueleto atual (header/hero/CSS/templates, validação de e-mail, padrão de POST e `secrets`). Mudanças:

1. **Uploader:** aceitar `pdf` (hoje: `xlsx/xlsb/csv`).
2. **POST 1:** reusar `montar_payload` (já faz base64 + JSON) apontando para o webhook de extração.
3. **Tela de seleção:** renderizar os itens retornados; por item, um `st.radio`/`selectbox` com candidatos + "criar novo".
4. **POST 2:** montar o JSON de decisão e enviar para o webhook de importação.
5. **Resultado:** exibir sucesso/erros do `IncluirNotaEnt`.
6. Front **não** ganha nenhuma lógica de PDF/Omie — continua só apresentação.

---

## 9. Pontos em aberto (decisões pendentes)

1. **Regra do `nValUnit`** (composição/rateio do valor contábil) — §7.
2. **`cCodCateg`** — categoria contábil da nota de entrada.
3. **`codigo_local_estoque`** — local de estoque.
4. **`cGeraFinanceiro` / `nCodCC`** — a nota gera financeiro? Qual conta?
5. **CFOP** — fixo `3556` ou varia por item?
6. **Tributos no item** — vêm do cadastro do produto (defaults) ou calculados a partir da DUIMP?
7. **Autenticação Omie** — `app_key`/`app_secret` (credencial no n8n).
8. **Fornecedor MOKO** — já cadastrado no Omie? Buscar por qual chave (razão social / documento exterior)?

---

## 10. Próximos passos

1. Você revisa este blueprint e responde os pontos do §9.
2. Eu monto o fluxo no n8n (2 webhooks) e adapto o `app.py`.
3. Testamos com esta DUIMP (26BR0000407051-9) e conferimos o resultado contra o XML modelo.
