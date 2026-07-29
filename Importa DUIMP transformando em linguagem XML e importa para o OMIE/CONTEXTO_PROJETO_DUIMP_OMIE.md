# Contexto do Projeto — DUIMP → Omie (handoff)

Resumo completo do que foi feito e do que falta, para retomar em nova sessão.

---

## 1. Objetivo

Automatizar a criação da **nota de entrada no Omie** a partir de uma **DUIMP**, consultando a **API do Portal Único Siscomex**. A nota de entrada é o registro contábil da importação.

> Evolução do escopo: começou como "PDF da DUIMP → gerar XML". Descobrimos que a **DUIMP não devolve XML** (só PDF). Depois achamos a **API do Portal Único**, que devolve tudo estruturado. **Decisão final: descartar a geração de XML e criar a nota direto no Omie via API (`IncluirNotaEnt`).**

---

## 2. Arquitetura atual

```
Front (Streamlit, FrontWebDuimpOmie) — usuário informa Nº da DUIMP + email
   │  POST JSON ao webhook
   ▼
n8n (workflow BiB66qG1EN6lGsrk, projeto Sillion, ATIVO)
   1. Autentica no Portal Único (chave-acesso)
   2. Consulta a DUIMP (dados gerais + itens, com tributos)
   3. [A FAZER] Resolve fornecedor + produtos no Omie e cria a nota (IncluirNotaEnt)
   ▼
Omie — nota de entrada criada
```

- **Webhook produção:** `https://sbrgui.app.n8n.cloud/webhook/duimp-xml`
- **Workflow URL:** https://sbrgui.app.n8n.cloud/workflow/BiB66qG1EN6lGsrk

---

## 3. Front (Streamlit) — PRONTO

- Pasta: `FrontWebDuimpOmie/` (repo unificado dentro de `autom_Duimp`).
- `app.py` adaptado: coleta **email + número da DUIMP + versão** e faz POST ao webhook. (Versão antiga de upload de PDF foi descartada.)
- Secret `N8N_WEBHOOK_URL` = a URL de produção acima (configurar no Streamlit Cloud).
- Deploy no Streamlit Cloud: repo `Automacao-Sillion/autom_Duimp`, branch `main`, **Main file path:** `FrontWebDuimpOmie/app.py`.

---

## 4. n8n — workflow atual (BiB66qG1EN6lGsrk)

Nós existentes e funcionando:
1. **Receber DUIMP** (Webhook POST `duimp-xml`)
2. **Config (Client-Id e Secret)** (Set) — campos editáveis: `clientId`, `clientSecret`, `baseUrl`, `numeroDuimp`, `versao`, `email`
3. **Autenticar (chave-acesso)** (HTTP POST) — headers `Client-Id`, `Client-Secret`, `Role-Type: IMPEXP`; `fullResponse` ligado
4. **Extrair Tokens** (Set) — pega `set-token` e `x-csrf-token` dos headers
5. **Consultar Dados Gerais**, **Consultar Itens** (HTTP GET) — funcionando
6. ~~Consultar Valores Calculados~~ → **REMOVER** (só funciona em DUIMP "em elaboração"; erro DIMP-ER8505 em DUIMP desembaraçada)
7. ~~Gerar XML / Enviar XML por Email~~ → **REMOVER** (XML descartado)

**A FAZER:** adicionar nó **"Criar Nota Omie"** (código pronto em `NODE_CriarNotaOmie.js`) ligado depois de **Consultar Itens**.

`baseUrl` atual = **produção** `https://portalunico.siscomex.gov.br`.

---

## 5. API do Portal Único (DUIMP)

**Autenticação** (base `{ambiente}/portal/`):
- `POST /api/autenticar/chave-acesso` com headers **`Client-Id`**, **`Client-Secret`**, **`Role-Type: IMPEXP`**.
- Resposta: headers `Set-Token` (JWT, vai como `Authorization`) e `X-CSRF-Token` (renova a cada chamada, 60 min).
- **Perfil IMPEXP exige e-CPF** (pessoa física habilitada a representar o importador). e-CNPJ **não** funciona (erro PLAT-ER2008).
- Chave gerada no portal: tipo **Pessoa Física**, perfil IMPEXP. As chaves são **por ambiente** (produção ≠ validação).
- Ambientes: produção `portalunico.siscomex.gov.br` · validação `val.portalunico.siscomex.gov.br`.

**Consulta** (base `https://portalunico.siscomex.gov.br/duimp-api/api/ext`, perfil IMPEXP):
- `GET /duimp/{numero}/versoes` — versão vigente
- `GET /duimp/{numero}/{versao}` — dados gerais
- `GET /duimp/{numero}/{versao}/itens` — **itens com tributos** (é a fonte principal)
- `GET /duimp/{numero}/{versao}/itens/{n}` — item específico
- `GET /duimp/chaves-acesso/importadores/{cnpj}` — **lista DUIMPs do importador** (permite fluxo automático sem digitar número)
- `GET .../valores-calculados` — **NÃO usar** (só DUIMP em elaboração)

---

## 6. Estrutura da resposta `/itens` (campos usados)

Cada item traz:
- `identificacao.numeroItem`, `produto.codigo` (1,2,3..), `produto.ncm`
- `mercadoria`: `quantidadeComercial`, `unidadeComercial`, `pesoLiquido`, `valorUnitarioMoedaNegociada`, `moedaNegociada.codigo`
- `condicaoVenda`: `valorBRL` (FOB R$), `valorMoedaNegociada` (FOB US$), `frete.valorBRL`, `seguro.valorBRL`, `incoterm.codigo`
- `tributos.mercadoria.valorAduaneiroBRL`
- `tributos.tributosCalculados[]` — por tipo (`II`/`IPI`/`PIS`/`COFINS`): `valoresBRL.devido` e `memoriaCalculo.valorAliquota` + `memoriaCalculo.baseCalculoBRL`
- **Descrição do produto vem `null`** (não está na API; vem do cadastro do Omie).

---

## 7. Mapeamento DUIMP → Omie `IncluirNotaEnt`

`produtos[]` (1 item da DUIMP = 1 item da nota):
| Omie | Origem |
|---|---|
| `cNCM` | `produto.ncm` |
| `nQtde` | `mercadoria.quantidadeComercial` |
| `nValUnit` | (decisão em aberto — ver §10) |
| `nCodProd` | resolver por NCM (usa se existir, cria se não) |
| `cCFOP` | `3.556` (default) |
| `PIS`/`COFINS`/etc | da DUIMP ou cadastro |

`cabec`: `cCodIntNotaEnt` (= "DUIMP-"+numero), `nCodCli` (fornecedor MOKO), `cGeraFinanceiro` "N".
`infAdic`: `cCodCateg` (categoria), `cDadosAdic` (resumo dos tributos no texto, espelhando a nota modelo).

Lógica de produto (decidida): **busca por NCM** no Omie → se existir usa o `codigo_produto`; se não existir, **cria** (`UpsertProduto`) com o NCM da DUIMP. O fluxo retorna, por item, se **criou** ou **mapeou**.

---

## 8. Regra de cálculo validada (contraprova)

Reconstruímos os valores da DUIMP a partir dos dados crus e bateu **ao centavo** com a API:
1. Frete rateado por **peso líquido**.
2. Valor aduaneiro = FOB (US$ × taxa) + frete.
3. II/IPI por NCM; PIS 2,10%; COFINS 9,65% sobre o aduaneiro.
4. Base ICMS = (aduaneiro + II + IPI + PIS + COFINS + Siscomex) ÷ 0,82 (ICMS 18% "por dentro").

**ICMS não está na DUIMP** (é estadual — status "Aguardando Tributos Estaduais"). Na nota modelo de vocês o ICMS aparece **zerado na linha** e o valor real só no campo de Informações Complementares. As diferenças entre nota e DUIMP (R$ 983 e R$ 1.948) são **despesas/"Outros"** acrescidos na criação da NF, não vêm da DUIMP.

---

## 9. Decisões já tomadas

- Input do front = **número da DUIMP** (não PDF).
- Autenticação Omie/Portal: **chave-acesso** (não certificado mTLS), **e-CPF**, **produção**.
- Produto no Omie: **por NCM**, usa ou cria.
- **XML descartado**; criar nota direto via `IncluirNotaEnt`.
- `cGeraFinanceiro` = N; CFOP padrão `3.556`; tributos no texto (infAdic) espelhando a nota modelo.

---

## 10. Decisões em aberto (resolver na nova sessão)

1. **`nValUnit` (valor do item):** aduaneiro (ex. item1 = R$ 49.603,32) **ou** contábil com ICMS por dentro (R$ 76.278,15)? (usuário disse "valor total" — confirmar qual).
2. **Endpoint do `IncluirNotaEnt`** — assumi `https://app.omie.com.br/api/v1/produtos/notaentrada/`; confirmar.
3. **CST de PIS/COFINS** no item (coloquei `98` placeholder).
4. **`cCodCateg`** (categoria) e **`codigo_local_estoque`** — buscar via API do Omie (Categorias/Estoque) ou informar.
5. **Padrão do código de produto novo** (usei `DUIMP-<ncm>`; usuário pode querer o padrão `PRD######`).
6. **Fornecedor MOKO** — buscar por `razao_social` "MOKO" (`ListarClientesResumido`) ou usar `nCodCli` fixo.

---

## 11. Arquivos do projeto (pasta "Importa DUIMP...")

- `NODE_CriarNotaOmie.js` — **código do nó n8n** que cria a nota (fornecedor + produto por NCM + IncluirNotaEnt; `dryRun` de segurança).
- `BLUEPRINT_DUIMP_OMIE.md` — arquitetura e mapeamento.
- `ESTRUTURA_XML_DI_DUIMP.md` — estrutura do XML antigo da DI (referência histórica).
- `PLANO_API_DUIMP_PORTALUNICO.md` — plano da integração com a API.
- `DUIMP_26BR0000407051-9_REAL.xml` / `TESTE_*.xml` — XMLs gerados (escopo descartado, manter como referência).
- `FrontWebDuimpOmie/` — front Streamlit.

---

## 12. DUIMPs de teste

- **26BR0000407051-9** (v1) — 6 itens. Total aduaneiro R$ 142.523,10; II 18.320,13; IPI 11.325,03; PIS 2.992,98; COFINS 13.753,47.
- **26BR0000966729-7** (v1) — 3 itens (NCM 8543.90.90, 8529.10.90, 8529.90.40). Total aduaneiro R$ 42.950,55.

---

## 13. Credenciais / cadastros no n8n (projeto Sillion)

- Gmail (vários), `OMIE_AUTH` (httpCustomAuth), `omie_sillion` (httpBearerAuth) — para autenticar no Omie (app_key/app_secret).
- As chaves do Portal Único (`clientId`/`clientSecret`) estão como **campos editáveis no nó Config** (a pedido do usuário).

---

## 14. Limitações conhecidas

- **MCP do n8n** parou de responder na sessão atual; por isso a etapa de criar a nota ficou pronta como **código pra colar** (`NODE_CriarNotaOmie.js`) em vez de inserida via ferramenta. Em nova sessão, com o conector reconectado, dá pra montar direto.
- Pasta é **OneDrive** — operações de `.git` e remoção de arquivos pelo sandbox falham (permissão); fazer pelo PC.

---

## 15. Próximo passo imediato

1. (Nova sessão, n8n reconectado) Ler o workflow `BiB66qG1EN6lGsrk` sem apagar as chaves.
2. Remover nós de XML/e-mail e o "Consultar Valores Calculados".
3. Adicionar o nó "Criar Nota Omie" (de `NODE_CriarNotaOmie.js`) depois de "Consultar Itens"; adicionar os campos no Config (`omieAppKey`, `omieAppSecret`, `cCodCateg`, `cfop`, `fornecedorBusca`, `dryRun`).
4. Resolver as decisões do §10.
5. Rodar com `dryRun=S` (mostra payload), conferir, e então `dryRun=N` para criar a nota. Testar com `26BR0000966729-7`.
