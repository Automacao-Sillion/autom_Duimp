# Estrutura do XML oficial da DI/DUIMP (Siscomex)

> Extração da estrutura do XML `ListaDeclaracoes` (formato Siscomex). Este é o **input ideal** para o processo: cada adição já traz todas as alíquotas e valores de tributos, base de cálculo, frete e mercadoria — sem precisar parsear o PDF nem buscar alíquotas faltantes.

---

## 1. Hierarquia

```
ListaDeclaracoes
└── declaracaoImportacao            (1 declaração)
    ├── adicao  [1..N]              ← uma por NCM/adição
    │   └── mercadoria [1..N]       ← itens comerciais da adição
    ├── importador
    ├── icms [1..N]
    ├── documentoInstrucaoDespacho [1..N]
    ├── pagamento [1..N]
    ├── embalagem / armazem / dossie
    └── informacaoComplementar      (texto livre: resumo de valores e adições)
```

Importante: **os tributos ficam no nível da `adicao`** (não da mercadoria). Quando uma adição tem várias mercadorias (mesmo NCM), os valores da adição são rateados entre elas por `valorUnitario × quantidade`.

---

## 2. Campos por seção (os que importam para a nota de entrada)

### `adicao` — valoração e mercadoria
| Campo | Significado |
|---|---|
| `numeroAdicao` | Nº da adição (001, 002...) |
| `dadosMercadoriaCodigoNcm` | **NCM** |
| `dadosMercadoriaNomeNcm` | Descrição do NCM |
| `dadosMercadoriaPesoLiquido` | Peso líquido da adição |
| `condicaoVendaIncoterm` / `condicaoVendaLocal` | Incoterm (EXW) e local |
| `condicaoVendaMoedaNome` | Moeda (DOLAR DOS EUA) |
| `condicaoVendaValorMoeda` | **FOB em moeda** (US$) |
| `condicaoVendaValorReais` | **FOB em R$** |
| `freteValorReais` / `seguroValorReais` | Frete e seguro da adição em R$ |
| `fabricanteNome` / `fornecedorNome` | Fabricante e exportador (MOKO) |
| `paisOrigemMercadoriaNome` | País de origem |

### `adicao` — tributos (tudo já calculado)
| Campo | Significado |
|---|---|
| `iiBaseCalculo` | **Base de cálculo do II = valor aduaneiro da adição** |
| `iiAliquotaAdValorem` | Alíquota do II (%) |
| `iiAliquotaValorDevido` | Valor do II (R$) |
| `ipiAliquotaAdValorem` / `ipiAliquotaValorDevido` | Alíquota e valor do IPI |
| `pisPasepAliquotaAdValorem` / `pisPasepAliquotaValorDevido` | Alíquota e valor do PIS |
| `cofinsAliquotaAdValorem` / `cofinsAliquotaValorDevido` | Alíquota e valor do COFINS |
| `pisCofinsBaseCalculoValor` | Base de cálculo de PIS/COFINS |

### `adicao › mercadoria` — item comercial
| Campo | Significado |
|---|---|
| `numeroSequencialItem` | Sequência do item dentro da adição |
| `descricaoMercadoria` | Descrição do produto |
| `quantidade` | Quantidade |
| `unidadeMedida` | Unidade (PECA...) |
| `valorUnitario` | Valor unitário (na moeda) |

### Cabeçalho da declaração
| Campo | Significado |
|---|---|
| `numeroDI` | Número da DI |
| `dataRegistro` / `dataDesembaraco` | Datas (AAAAMMDD) |
| `totalAdicoes` | Total de adições |
| `importadorNumero` / `importadorNome` | CNPJ e nome do importador (SILLION) |
| `cargaPesoLiquido` / `cargaPesoBruto` | Pesos totais |
| `cargaPaisProcedenciaNome` / `cargaDataChegada` | Procedência e chegada |
| `freteTotalReais` / `seguroTotalReais` | Totais de frete/seguro |
| `icms › valorTotalIcms` / `ufIcms` | ICMS recolhido |
| `documentoInstrucaoDespacho` | Fatura comercial, conhecimento, romaneio |
| `pagamento › codigoReceita` / `valorReceita` | Tributos recolhidos por código de receita |

---

## 3. Codificação dos números (atenção!)

Os valores vêm **sem vírgula, com zeros à esquerda e casas decimais implícitas**. Conversões confirmadas contra o "RESUMO DE VALORES" do próprio XML:

| Tipo de campo | Regra | Exemplo (cru → real) |
|---|---|---|
| Valores em R$ (`*ValorReais`, `*BaseCalculo`, `*ValorDevido`, `valorTotalIcms`) | ÷ 100 (2 decimais) | `000000015336815` → **R$ 153.368,15** |
| Alíquotas ad valorem (II/IPI/PIS/COFINS) | ÷ 100 (% com 2 decimais) | `01260` → **12,60%**; `01045` → **10,45%**; `00210` → **2,10%** |
| Pesos (`*PesoLiquido`) | ÷ 1.000.000 (6 decimais) | `000000009150000` → **9,150000 kg** |
| Quantidade (`quantidade`, `*MedidaEstatisticaQuantidade`) | ÷ 1.000.000 | `00000030000000` → **30** |
| Valor unitário (`valorUnitario`) | ÷ 1.000.000 (validar pelo layout) | `...002150000` → **US$ 2,15** (×120 = US$ 258 ✓) |
| Datas | AAAAMMDD | `20251216` → 16/12/2025 |

> As escalas exatas devem ser confirmadas no leiaute oficial do Siscomex, mas as acima reproduzem o resumo do XML ao centavo.

---

## 4. Por que isso resolve o problema anterior

Com o **PDF** só tínhamos a base de cálculo de 2 dos 6 itens e faltavam alíquotas de II/IPI de 2 NCMs. Com **este XML**, cada adição traz:

- `iiBaseCalculo` = valor aduaneiro exato por adição;
- alíquotas e valores de **II, IPI, PIS, COFINS** já calculados;
- frete e FOB por adição.

Ou seja, dá pra montar o valor do item (e a base de ICMS, aplicando o ICMS "por dentro") **de forma exata e para todos os itens**, sem reconstrução nem arredondamento inventado.

---

## 5. Mapeamento adicao/mercadoria → item da nota Omie (visão)

```
adicao.mercadoria  →  1 item da nota
  NCM        ← dadosMercadoriaCodigoNcm
  qtde       ← mercadoria.quantidade
  descrição  ← mercadoria.descricaoMercadoria  (e/ou produto do cadastro Omie por NCM)
  valor      ← FOB (condicaoVendaValorReais) + frete (freteValorReais) + tributos da adição,
               rateados por valorUnitario×quantidade quando a adição tem vários itens
```

---

## 6. Pendência aberta

Este XML de exemplo é de **outra importação** (DI 2527947343 — bafômetros). Para gerar a nota da nossa DUIMP (`26BR0000407051-9`), preciso do **XML equivalente dessa DUIMP**. Pergunta: o despachante/Siscomex consegue te fornecer este XML para a DUIMP em questão (e para as próximas)? Se sim, o processo inteiro passa a ler o XML — bem mais simples e exato que o PDF.
