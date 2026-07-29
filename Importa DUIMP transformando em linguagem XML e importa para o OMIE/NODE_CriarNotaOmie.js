// ============================================================
// n8n · Code node "Criar Nota Omie"  (mode: Run Once for All Items)
// Liga depois de "Consultar Itens". Resolve fornecedor e produto
// nas APIs do Omie e monta/envia o IncluirNotaEnt.
//
// Campos a adicionar no nó "Config (Client-Id e Secret)":
//   omieAppKey, omieAppSecret  -> credenciais Omie (app_key/app_secret)
//   cCodCateg                  -> categoria contábil da nota (ex.: 1.01.02)
//   codigoLocalEstoque         -> código do local de estoque (opcional)
//   cfop                       -> CFOP (default 3.556)
//   fornecedorBusca            -> nome p/ achar o fornecedor (default MOKO)
//   dryRun                     -> "S" só monta o payload | "N" cria a nota de verdade
//   (opcionais) nCodCli, dPrevisao
// ============================================================
const H = this.helpers;
const cfg = $('Config (Client-Id e Secret)').first().json;

const APP_KEY    = cfg.omieAppKey;
const APP_SECRET = cfg.omieAppSecret;
const CCODCATEG  = cfg.cCodCateg || '';
const LOCAL_EST  = cfg.codigoLocalEstoque ? Number(cfg.codigoLocalEstoque) : undefined;
const CFOP       = cfg.cfop || '3.556';
const FORN_BUSCA = cfg.fornecedorBusca || 'MOKO';
const DRY_RUN    = String(cfg.dryRun == null ? 'S' : cfg.dryRun).toUpperCase() !== 'N';

const URL_CLI  = 'https://app.omie.com.br/api/v1/geral/clientes/';
const URL_PROD = 'https://app.omie.com.br/api/v1/geral/produtos/';
const URL_NE   = 'https://app.omie.com.br/api/v1/produtos/notaentrada/';

async function omie(url, call, param) {
  return await H.httpRequest({ method: 'POST', url, json: true,
    body: { call, app_key: APP_KEY, app_secret: APP_SECRET, param: [param] } });
}
const ncmDot = s => { const d = String(s || '').replace(/\D/g, ''); return d.length === 8 ? d.slice(0,4)+'.'+d.slice(4,6)+'.'+d.slice(6) : d; };
const ft  = (it, t) => ((it.tributos && it.tributos.tributosCalculados) || []).find(x => x.tipo === t) || {};
const dev = t => (t.valoresBRL && t.valoresBRL.devido != null) ? Number(t.valoresBRL.devido) : 0;

const itens = $('Consultar Itens').all().map(i => i.json);

// 1) Fornecedor (por nome) ou nCodCli fixo no Config
let nCodCli = cfg.nCodCli ? Number(cfg.nCodCli) : null;
if (!nCodCli) {
  const r = await omie(URL_CLI, 'ListarClientesResumido', { pagina: 1, registros_por_pagina: 50, clientesFiltro: { razao_social: FORN_BUSCA } });
  const lst = (r && r.clientes_cadastro_resumido) || [];
  if (!lst.length) throw new Error('Fornecedor nao encontrado no Omie: ' + FORN_BUSCA);
  nCodCli = lst[0].codigo_cliente;
}

// 2) Produtos por NCM (usa se existir, cria se nao) + itens da nota
const produtos = [];
const relatorio = [];
for (const it of itens) {
  const ncm = it.produto && it.produto.ncm;
  const m = it.mercadoria || {};
  const tm = (it.tributos && it.tributos.mercadoria) || {};
  const qtde = Number(m.quantidadeComercial || 0);
  const aduaneiro = Number(tm.valorAduaneiroBRL || 0);
  const valUnit = qtde ? Number((aduaneiro / qtde).toFixed(10)) : 0;

  const pr = await omie(URL_PROD, 'ListarProdutosResumido', { pagina: 1, registros_por_pagina: 50, ncm: ncmDot(ncm) });
  const lst = (pr && pr.produto_servico_resumido) || [];
  let nCodProd, acao;
  if (lst.length) { nCodProd = lst[0].codigo_produto; acao = 'mapeado'; }
  else {
    const novo = await omie(URL_PROD, 'UpsertProduto', {
      codigo: 'DUIMP-' + ncm,
      codigo_produto_integracao: 'DUIMP-' + ncm,
      descricao: 'Produto NCM ' + ncm + ' (importado via DUIMP)',
      unidade: (m.unidadeComercial || 'UN').slice(0, 6),
      ncm: ncmDot(ncm), origem_imposto: '1'
    });
    nCodProd = novo.codigo_produto; acao = 'criado';
  }
  relatorio.push({ item: it.identificacao && it.identificacao.numeroItem, ncm, acao, nCodProd });

  const prod = {
    cCodItInt: 'IT' + (it.identificacao && it.identificacao.numeroItem),
    nCodProd, cCFOP: CFOP, nQtde: qtde, nValUnit: valUnit, cNCM: ncmDot(ncm),
    PIS: { cSitTribPIS: '98' }, COFINS: { cSitTribCOFINS: '98' }
  };
  if (LOCAL_EST) prod.codigo_local_estoque = LOCAL_EST;
  produtos.push(prod);
}

// 3) Cabecalho + infAdic (tributos no texto, igual a nota modelo)
const numeroDuimp = cfg.numeroDuimp || (itens[0] && itens[0].identificacao && itens[0].identificacao.numero);
const resumo = itens.map(it => {
  const n = it.identificacao && it.identificacao.numeroItem;
  return 'Item ' + n + ' NCM ' + (it.produto && it.produto.ncm) +
    ': II ' + dev(ft(it,'II')).toFixed(2) + ' IPI ' + dev(ft(it,'IPI')).toFixed(2) +
    ' PIS ' + dev(ft(it,'PIS')).toFixed(2) + ' COFINS ' + dev(ft(it,'COFINS')).toFixed(2);
}).join(' || ');

const payload = {
  cabec: { cCodIntNotaEnt: 'DUIMP-' + numeroDuimp, nCodCli: nCodCli, cGeraFinanceiro: 'N' },
  infAdic: { cCodCateg: CCODCATEG, cDadosAdic: 'DUIMP ' + numeroDuimp + ' | ' + resumo },
  produtos: produtos
};
if (cfg.dPrevisao) payload.cabec.dPrevisao = cfg.dPrevisao;

if (DRY_RUN) return [{ json: { dryRun: true, nCodCli, relatorio, payload } }];
const resp = await omie(URL_NE, 'IncluirNotaEnt', payload);
return [{ json: { dryRun: false, nCodCli, relatorio, resposta: resp } }];
