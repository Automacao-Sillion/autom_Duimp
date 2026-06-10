# autom_Duimp — Importação de DUIMP → XML → Omie

Automação que transforma uma **DUIMP** (Declaração Única de Importação) em um **XML estruturado** (no molde do antigo XML da DI do Siscomex) para importação no **Omie** como nota de entrada.

## Contexto

A DUIMP (novo sistema do Portal Único) **não devolve mais um XML** como a antiga DI — só o extrato em PDF. Esta automação resolve isso consultando a **API do Portal Único Siscomex** e montando o XML a partir dos dados oficiais (itens, NCM e tributos calculados por item), sem depender da leitura do PDF.

## Fluxo

```
Front (Streamlit): informa o número da DUIMP + email
   → n8n (webhook):
        1. Autentica no Portal Único (chave-acesso: Client-Id / Client-Secret / Role-Type=IMPEXP)
        2. Consulta dados gerais, itens e valores-calculados da DUIMP
        3. Monta o XML (molde DI)
        4. Envia o XML por email
```

## Estrutura do projeto

```
autom_Duimp/
└── Importa DUIMP transformando em linguagem XML e importa para o OMIE/
    ├── BLUEPRINT_DUIMP_OMIE.md            # arquitetura e mapeamento DUIMP → Omie
    ├── ESTRUTURA_XML_DI_DUIMP.md          # estrutura do XML oficial da DI/DUIMP
    ├── PLANO_API_DUIMP_PORTALUNICO.md     # plano de integração com a API do Portal Único
    ├── TESTE_DUIMP_26BR0000407051-9.xml   # XML de teste gerado (molde DI)
    └── FrontWebDuimpOmie/                 # front em Streamlit
```

## Componentes

- **Front (Streamlit):** `FrontWebDuimpOmie/` — coleta o número da DUIMP e o email e envia ao webhook do n8n.
- **Backend (n8n):** workflow "DUIMP - Consulta Portal Unico e Geracao de XML" (projeto Sillion).
- **API DUIMP:** Portal Único Siscomex — base `https://portalunico.siscomex.gov.br/duimp-api/api/ext` (perfil `IMPEXP`).

## Documentação

Os detalhes de arquitetura, mapeamento de campos, codificação dos valores e endpoints estão nos arquivos `.md` da pasta do projeto.

## Segurança

- As chaves de acesso do Portal Único (`Client-Id` / `Client-Secret`) **não ficam no código** — são preenchidas no n8n.
- O `.gitignore` bloqueia segredos, certificados e planilhas de teste.

> Projeto interno — Automacao-Sillion.
