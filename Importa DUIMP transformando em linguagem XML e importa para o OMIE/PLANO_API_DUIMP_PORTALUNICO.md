# Integração via API do Portal Único (DUIMP) — Plano

> A DUIMP tem API REST no Portal Único Siscomex. Isso substitui a leitura do PDF: consultamos a DUIMP por número e recebemos tudo estruturado e **com os tributos oficiais já calculados por item**. Fim da dedução de alíquotas e do problema do PDF truncado.

---

## 1. Nova arquitetura

```
Streamlit: usuário informa o NÚMERO da DUIMP (+ email)   ← não precisa mais subir PDF
   │ POST
   ▼
n8n:
  1. Autentica no Portal Único  → Set-Token + X-CSRF-Token
  2. GET versão vigente          (se não informada)
  3. GET dados gerais            /duimp/{n}/{v}
  4. GET itens                   /duimp/{n}/{v}/itens
  5. GET valores-calculados/item /duimp/{n}/{v}/itens/{i}/valores-calculados
  6. Monta o XML (molde DI) com dados 100% exatos
  7. Envia o XML por email
```

---

## 2. Autenticação

Base: `https://{ambiente}/portal/`
Ambientes: Validação `val.portalunico.siscomex.gov.br` · Produção `portalunico.siscomex.gov.br`

Dois modos:

- **Certificado digital (mTLS)** — `POST /api/autenticar` com handshake mTLS usando o e-CNPJ (A1/A3 ICP-Brasil). Header obrigatório `Role-Type: IMPEXP`.
- **Par de chaves de acesso** — `POST /api/autenticar/chave-acesso`. As chaves são geradas uma vez no portal e passadas por header; **não precisa embarcar o certificado A1**. ✅ Recomendado para o n8n (mais simples e seguro).

Resposta (headers):

| Header | Uso |
|---|---|
| `Set-Token` | JWT do usuário — enviar como `Authorization` nas próximas chamadas |
| `X-CSRF-Token` | Token anti-CSRF — enviar em todas as chamadas. **Renova a cada requisição** (vale 60 min); reaproveite o último recebido sem reautenticar. |
| `X-CSRF-Expiration` | Expiração do CSRF (ms) |

Observações:
- Perfil necessário: **IMPEXP** (Declarante importador/exportador), aceita **e-CNPJ**.
- Parada programada diária do Portal: **01:00–03:00** (API indisponível).
- Não reautenticar em menos de 60s (erro `PLAT-ER2033`).

---

## 3. Endpoints de consulta da DUIMP

Base: `https://portalunico.siscomex.gov.br/duimp-api/api/ext`
Perfil: **IMPEXP**

| Método/URI | Retorno |
|---|---|
| `GET /duimp/{numero}/versoes` | número da versão vigente |
| `GET /duimp/{numero}/{versao}` | dados gerais (importador, carga, frete, documentos) |
| `GET /duimp/{numero}/{versao}/itens` | faixa de itens (NCM, mercadoria, valores) |
| `GET /duimp/{numero}/{versao}/itens/{numero-item}` | um item específico |
| `GET /duimp/{numero}/{versao}/valores-calculados` | tributos totais calculados |
| `GET /duimp/{numero}/{versao}/itens/{numero-item}/valores-calculados` | **tributos por item: II, IPI, PIS, COFINS, base de cálculo e memória de cálculo** |
| `GET /duimp/chaves-acesso/importadores/{ni-importador}` | lista de DUIMPs de um importador |

Exemplo de URL completa (produção):
`https://portalunico.siscomex.gov.br/duimp-api/api/ext/duimp/26BR0000407051-9/1`

---

## 4. O que muda no projeto

- **Front (Streamlit):** em vez de subir o PDF, o usuário só informa o **número da DUIMP** + email (mais simples). O PDF deixa de ser necessário.
- **n8n:** ganha a etapa de autenticação (chave-acesso) e as chamadas GET de consulta. A geração do XML continua igual ao molde validado, mas agora com dados **oficiais por item** — dispensa a reconstrução por peso e a dedução de alíquotas dos itens 5 e 6.
- **Confiabilidade:** valores idênticos aos da Receita; some o risco do "Outros" estimado.

---

## 5. Pontos a confirmar / preparar

1. **Modo de autenticação:** gerar o **par de chaves de acesso** no portal (recomendado) ou usar o certificado A1 via mTLS no n8n?
2. **Ambiente:** começar em **Validação** (`val.portalunico...`) para testes e depois Produção?
3. **n8n e mTLS:** se for por certificado, o HTTP Request do n8n precisa suportar client cert (ou usamos a chave-acesso para evitar isso).
4. **Front:** confirmar a mudança de "upload de PDF" para "informar número da DUIMP".
5. **Versão:** consultar sempre a versão vigente via `/versoes` antes de puxar os dados.
