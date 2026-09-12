/* ==========================================================================
   commercial_front.test.js — teste de front-end da camada comercial B2B.

   Roda contra o HTML GERADO em docs/ (nunca contra mocks): carrega cada página
   no jsdom, executa assets/commercial.js + assets/site.js e verifica analytics,
   preservação de UTM, lead scoring, validação do formulário, honeypot, captura
   nos dois modos (provider HTTP e fallback) e a integridade das páginas do
   monitor público.

   Dependência de desenvolvimento (não usada em produção nem no site):
       npm install --no-save jsdom
   Execução:
       node scripts/tests/commercial_front.test.js            # modo auto-detectado
       node scripts/tests/commercial_front.test.js endpoint   # força um modo
   Chamado automaticamente por scripts/selftest_comercial.py quando node+jsdom
   estão disponíveis (caso contrário é pulado, sem falhar).
   ========================================================================== */
'use strict';
const { JSDOM, VirtualConsole } = require('jsdom');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
function detectarModo() {
  const html = fs.readFileSync(path.join(ROOT, 'docs/diagnostico/index.html'), 'utf8');
  const m = html.match(/<script id="monitor-commercial-config" type="application\/json">([\s\S]*?)<\/script>/);
  const cfg = m ? JSON.parse(m[1]) : {};
  return (cfg.leadEndpoint ? 'endpoint' : 'fallback');
}
// modo pode ser forçado por argumento; por padrão é detectado do build atual
const MODO = (process.argv[2] === 'fallback' || process.argv[2] === 'endpoint')
  ? process.argv[2] : detectarModo();
let falhas = 0, ok = 0;

function check(nome, cond, extra) {
  if (cond) { ok++; console.log('  ok   · ' + nome); }
  else { falhas++; console.log('  FALHA· ' + nome + (extra ? ' → ' + extra : '')); }
}

function carregar(rel, url) {
  const html = fs.readFileSync(path.join(ROOT, rel), 'utf8');
  const erros = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => {
    // navegação mailto (modo fallback) não é implementada no jsdom — esperado
    if (/Not implemented: navigation/.test(e.message)) return;
    erros.push(e.message);
  });
  vc.on('error', (...a) => erros.push(String(a)));
  const dom = new JSDOM(html, {
    url, runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole: vc
  });
  const w = dom.window;
  w.fetchCalls = [];
  w.fetch = (u, opts) => { w.fetchCalls.push({ u, opts }); return Promise.resolve({ ok: true, json: () => Promise.resolve({}) }); };
  w.navigator.sendBeacon = () => true;
  w.HTMLFormElement.prototype.submit = function () { w.nativeSubmit = true; };
  // mesma ordem do documento: commercial.js (head, defer) e site.js (fim do body, defer)
  w.eval(fs.readFileSync(path.join(ROOT, 'scripts/assets/commercial.js'), 'utf8'));
  w.eval(fs.readFileSync(path.join(ROOT, 'scripts/assets/site.js'), 'utf8'));
  return { w, erros };
}

function eventos(w) { return (w.dataLayer || []).map(e => e.event); }
function ultimo(w, nome) {
  const lista = (w.dataLayer || []).filter(e => e.event === nome);
  return lista[lista.length - 1];
}
function preencher(w, nome, valor) {
  const el = w.document.querySelector('[name="' + nome + '"]');
  if (!el) return false;
  if (el.type === 'checkbox') el.checked = (valor === true || valor === 'sim');
  else el.value = valor;
  el.dispatchEvent(new w.Event('input', { bubbles: true }));
  el.dispatchEvent(new w.Event('change', { bubbles: true }));
  return true;
}

(async function () {
  console.log('\n== 1) /diagnostico/ — analytics, UTM e lead scoring (modo ' + MODO + ') ==');
  const utm = '?utm_source=linkedin&utm_medium=cpc&utm_campaign=radar_ia&utm_content=cta_topo';
  const { w, erros } = carregar('docs/diagnostico/index.html',
    'https://monitor.lcfconsulting.com.br/diagnostico/' + utm);

  check('sem erro de console na carga', erros.length === 0, erros.join(' | '));
  check('dataLayer criado', Array.isArray(w.dataLayer));
  check('page_view disparado', eventos(w).includes('page_view'));
  check('diagnostic_page_view disparado', eventos(w).includes('diagnostic_page_view'));
  const pv = ultimo(w, 'page_view');
  check('UTM preservado no evento (source)', pv && pv.utm_source === 'linkedin', JSON.stringify(pv && pv.utm_source));
  check('UTM preservado no evento (campaign)', pv && pv.utm_campaign === 'radar_ia');
  check('origem derivada do UTM', pv && pv.origem === 'linkedin');
  check('page_kind = lead_form', pv && pv.page_kind === 'lead_form');
  check('UTM persistido em localStorage', !!w.localStorage.getItem('monitor_utm'));

  // clique em CTA comercial
  const cta = w.document.querySelector('[data-track="commercial_cta_click"]');
  check('CTA comercial presente na página', !!cta);
  cta.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  check('commercial_cta_click disparado', eventos(w).includes('commercial_cta_click'));

  // início do preenchimento
  preencher(w, 'nome', 'Ana Souza');
  check('diagnostic_started disparado', eventos(w).includes('diagnostic_started'));

  // perfil de PRIORIDADE COMERCIAL (esperado: 100 pontos)
  preencher(w, 'empresa', 'Banco Exemplo S.A.');
  preencher(w, 'cargo', 'Diretor(a)');
  preencher(w, 'email', 'ana.souza@bancoexemplo.com.br');
  preencher(w, 'telefone', '+55 11 98888-7777');
  preencher(w, 'setor', 'Bancos');
  preencher(w, 'tamanho', 'Mais de 1.000');
  preencher(w, 'uso_ia', 'IA em processo crítico da operação');
  preencher(w, 'area', 'Sim — Compliance');
  preencher(w, 'horizonte', 'Imediata — próximos 3 meses');
  preencher(w, 'preocupacao', 'Marco legal da IA (PL 2338/2023)');
  preencher(w, 'interesse', 'Diagnóstico de Exposição Regulatória');
  preencher(w, 'consentimento', true);

  const dbg = w.document.querySelector('[data-lead-debug]');
  if (dbg) { dbg.hidden = false; }
  const form = w.document.getElementById('form-diagnostico');
  form.dispatchEvent(new w.Event('submit', { bubbles: true, cancelable: true }));
  await new Promise(r => setTimeout(r, 60));

  const score = w.document.querySelector('[data-lead-score]').value;
  const classe = w.document.querySelector('[data-lead-class]').value;
  check('lead score = 100 para perfil prioridade', score === '100', 'obtido: ' + score);
  check('classificação = prioridade_comercial', /prioridade_comercial/.test(classe), classe);
  const fatores = JSON.parse(w.document.querySelector('[data-lead-factors]').value || '[]');
  check('7 fatores registrados no score', fatores.length === 7, 'obtido: ' + fatores.length);

  const payload = JSON.parse(w.document.querySelector('[data-lead-payload]').value || '{}');
  check('payload tem e-mail corporativo', payload.email === 'ana.souza@bancoexemplo.com.br');
  check('payload tem página de origem', payload.pagina_origem === 'diagnostico/');
  check('payload tem UTM (campaign)', payload.utm_campaign === 'radar_ia');
  check('payload tem timestamp', /^\d{4}-\d{2}-\d{2}T/.test(payload.timestamp_envio || ''));
  check('payload tem _subject com score', /score 100/.test(payload._subject || ''), payload._subject);
  check('lead gravado em buffer local', (JSON.parse(w.localStorage.getItem('monitor_leads_local') || '[]')).length === 1);

  if (MODO === 'endpoint') {
    check('diagnostic_submitted disparado', eventos(w).includes('diagnostic_submitted'));
    const ev = ultimo(w, 'diagnostic_submitted');
    check('evento leva lead_score', ev && ev.lead_score === 100, JSON.stringify(ev));
    check('evento leva modo=endpoint', ev && ev.modo === 'endpoint');
    check('fetch chamou o provider', w.fetchCalls.length === 1 && /formspree\.io/.test(w.fetchCalls[0].u), JSON.stringify(w.fetchCalls.map(c => c.u)));
    check('painel de sucesso renderizado', !!w.document.querySelector('.form-ok'));
  } else {
    check('diagnostic_submitted disparado (fallback)', eventos(w).includes('diagnostic_submitted'));
    const ev = ultimo(w, 'diagnostic_submitted');
    check('evento leva modo=fallback', ev && ev.modo === 'fallback', JSON.stringify(ev));
    check('nenhum fetch sem provider configurado', w.fetchCalls.length === 0);
    check('painel de sucesso renderizado', !!w.document.querySelector('.form-ok'));
  }

  // validação: envio sem consentimento deve falhar
  console.log('\n== 2) Validação do formulário ==');
  const { w: w2 } = carregar('docs/diagnostico/index.html',
    'https://monitor.lcfconsulting.com.br/diagnostico/');
  preencher(w2, 'nome', 'Teste');
  const f2 = w2.document.getElementById('form-diagnostico');
  f2.dispatchEvent(new w2.Event('submit', { bubbles: true, cancelable: true }));
  await new Promise(r => setTimeout(r, 30));
  check('envio incompleto bloqueado', !w2.document.querySelector('.form-ok'));
  check('erro de validação instrumentado', eventos(w2).includes('diagnostic_validation_error'));
  check('campos obrigatórios marcados', w2.document.querySelectorAll('.field.invalid').length >= 3);

  // honeypot
  const { w: w3 } = carregar('docs/diagnostico/index.html',
    'https://monitor.lcfconsulting.com.br/diagnostico/');
  preencher(w3, '_gotcha', 'spam');
  ['nome', 'empresa', 'cargo', 'email', 'setor', 'tamanho', 'uso_ia', 'area', 'horizonte', 'preocupacao', 'interesse']
    .forEach((n, i) => {
      const el = w3.document.querySelector('[name="' + n + '"]');
      if (el && el.tagName === 'SELECT' && el.options.length > 1) el.value = el.options[1].value;
      else if (el) el.value = 'x' + i + '@empresa.com.br';
    });
  preencher(w3, 'consentimento', true);
  w3.document.getElementById('form-diagnostico').dispatchEvent(new w3.Event('submit', { bubbles: true, cancelable: true }));
  await new Promise(r => setTimeout(r, 30));
  check('honeypot bloqueia envio de bot', !w3.document.querySelector('.form-ok') && eventos(w3).includes('lead_bot_blocked'));

  console.log('\n== 3) /briefing-executivo/ — amostra, alerta e impressão ==');
  const { w: wb, erros: eb } = carregar('docs/briefing-executivo/index.html',
    'https://monitor.lcfconsulting.com.br/briefing-executivo/?utm_source=newsletter');
  check('sem erro de console', eb.length === 0, eb.join(' | '));
  check('briefing_sample_view disparado', eventos(wb).includes('briefing_sample_view'));
  const pvb = ultimo(wb, 'page_view');
  check('UTM de newsletter preservado', pvb && pvb.utm_source === 'newsletter');
  check('blocos fato oficial presentes', wb.document.querySelectorAll('.brief-col.fato').length >= 5);
  check('blocos análise presentes', wb.document.querySelectorAll('.brief-col.analise').length >= 5);
  check('separação fato × análise rotulada', wb.document.querySelectorAll('.tag-fato').length >= 5 && wb.document.querySelectorAll('.tag-analise').length >= 5);
  check('score exposto nos blocos', wb.document.querySelectorAll('.brief-item[data-score]').length >= 5);
  check('botão imprimir presente', !!wb.document.querySelector('[data-print-brief]'));
  wb.document.querySelector('[data-print-brief]').dispatchEvent(new wb.MouseEvent('click', { bubbles: true }));
  check('briefing_print instrumentado', eventos(wb).includes('briefing_print'));

  const alerta = wb.document.getElementById('form-alerta');
  check('formulário de alerta presente', !!alerta);
  preencher(wb, 'email', 'regulatorio@empresa.com.br');
  preencher(wb, 'setor', 'Seguros');
  preencher(wb, 'frequencia', 'semanal');
  preencher(wb, 'score_minimo', '80');
  const cb = alerta.querySelector('[name="consentimento"]');
  cb.checked = true;
  alerta.dispatchEvent(new wb.Event('submit', { bubbles: true, cancelable: true }));
  await new Promise(r => setTimeout(r, 60));
  check('alert_signup disparado', eventos(wb).includes('alert_signup'), eventos(wb).join(','));

  console.log('\n== 4) /solucoes/ e /para-empresas/ ==');
  const { w: ws } = carregar('docs/solucoes/index.html', 'https://monitor.lcfconsulting.com.br/solucoes/');
  check('pricing_view disparado', eventos(ws).includes('pricing_view'));
  check('4 planos renderizados', ws.document.querySelectorAll('[data-plan]').length >= 4);
  const { w: wp } = carregar('docs/para-empresas/index.html', 'https://monitor.lcfconsulting.com.br/para-empresas/');
  check('para_empresas_view disparado', eventos(wp).includes('para_empresas_view'));
  const demo = wp.document.querySelector('[data-track="demo_request"]');
  check('CTA de demo presente', !!demo);
  demo.dispatchEvent(new wp.MouseEvent('click', { bubbles: true }));
  check('demo_request disparado', eventos(wp).includes('demo_request'));

  console.log('\n== 5) página pública do monitor (não comercial) segue instrumentada ==');
  const { w: wh, erros: eh } = carregar('docs/index.html', 'https://monitor.lcfconsulting.com.br/');
  check('sem erro de console na home', eh.length === 0, eh.join(' | '));
  check('page_view na home', eventos(wh).includes('page_view'));
  check('faixa comercial na home', !!wh.document.querySelector('.commercial-band'));
  check('CTA do cabeçalho na home', !!wh.document.querySelector('.nav-cta'));
  const faixa = wh.document.querySelector('.commercial-band [data-track="commercial_cta_click"]');
  faixa.dispatchEvent(new wh.MouseEvent('click', { bubbles: true }));
  check('commercial_cta_click na faixa da home', eventos(wh).includes('commercial_cta_click'));

  console.log('\n== 6) filtros originais do monitor continuam funcionando ==');
  const { w: wl } = carregar('docs/proposicoes/index.html', 'https://monitor.lcfconsulting.com.br/proposicoes/');
  const linhas = wl.document.querySelectorAll('[data-prop]');
  check('lista de proposições renderizada', linhas.length > 100, 'n=' + linhas.length);
  const fScore = wl.document.getElementById('f-score');
  if (fScore) {
    fScore.value = '75';
    fScore.dispatchEvent(new wl.Event('input', { bubbles: true }));
    const visiveis = Array.prototype.filter.call(linhas, r => r.style.display !== 'none');
    const esperados = Array.prototype.filter.call(linhas, r => parseInt(r.dataset.score, 10) >= 75).length;
    check('filtro de score do monitor continua funcionando (site.js intacto)',
      visiveis.length === esperados && esperados > 0, 'visíveis=' + visiveis.length + ' esperados=' + esperados);
  } else {
    check('filtro de score existe', false);
  }

  console.log('\nRESULTADO: ' + ok + ' ok · ' + falhas + ' falha(s)');
  process.exit(falhas ? 1 : 0);
})();
