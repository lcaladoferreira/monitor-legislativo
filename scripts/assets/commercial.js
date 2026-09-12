/* ==========================================================================
   commercial.js — analytics comercial + captura de lead + lead scoring.

   Camada agnóstica de fornecedor (sem dependência de GA4/Plausible instalados):
     * eventos vão sempre para window.dataLayer (padrão GTM) e para um buffer
       local em localStorage (debug e auditoria do funil);
     * se houver GA4 configurado no build, chama gtag('event', ...);
     * se houver Plausible configurado, chama plausible(event, {props});
     * se houver endpoint próprio (MONITOR_ANALYTICS_ENDPOINT), faz sendBeacon.

   UTM é preservado (first touch + last touch) e enviado junto com o lead.
   Nenhum dado é enviado para terceiros além do que estiver configurado.
   ========================================================================== */
(function () {
  'use strict';

  var node = document.getElementById('monitor-commercial-config');
  var CFG = {};
  if (node) {
    try { CFG = JSON.parse(node.textContent || '{}'); } catch (e) { CFG = {}; }
  }
  var DEBUG = (CFG.analytics && CFG.analytics.debug) ||
    /[?&]debug=1/.test(location.search);
  var LS_UTM = 'monitor_utm';
  var LS_EVENTS = 'monitor_eventos';
  var LS_LEADS = 'monitor_leads_local';

  function nowIso() { return new Date().toISOString(); }

  function safeGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function safeSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* privado/anônimo */ } }

  /* ------------------------------------------------------------- UTM ---- */
  var UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'gclid', 'fbclid', 'ref'];

  function readUtm() {
    var q = new URLSearchParams(location.search);
    var atual = {};
    UTM_KEYS.forEach(function (k) {
      var v = q.get(k);
      if (v) atual[k] = v;
    });
    var guardado = {};
    var raw = safeGet(LS_UTM);
    if (raw) { try { guardado = JSON.parse(raw); } catch (e) { guardado = {}; } }
    if (Object.keys(atual).length) {
      // first touch preservado; last touch atualizado
      var first = guardado.first_touch || atual;
      guardado = { first_touch: first, last_touch: atual, atualizado_em: nowIso() };
      safeSet(LS_UTM, JSON.stringify(guardado));
    }
    return guardado;
  }

  function utmFlat(u) {
    var out = {};
    var lt = (u && u.last_touch) || {};
    var ft = (u && u.first_touch) || {};
    UTM_KEYS.forEach(function (k) {
      if (lt[k]) out[k] = lt[k];
      if (ft[k]) out['first_' + k] = ft[k];
    });
    out.origem = lt.utm_source || ft.utm_source || document.referrer || 'direto';
    out.campanha = lt.utm_campaign || ft.utm_campaign || '';
    return out;
  }

  var UTM = readUtm();

  /* --------------------------------------------------------- analytics ---- */
  var buffer = [];
  try { buffer = JSON.parse(safeGet(LS_EVENTS) || '[]'); } catch (e) { buffer = []; }

  function pushGtm(ev) {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push(ev);
  }

  function pushGa4(name, params) {
    if (!CFG.analytics || !CFG.analytics.ga4_id) return;
    if (typeof window.gtag === 'function') window.gtag('event', name, params);
  }

  function pushPlausible(name, props) {
    if (!CFG.analytics || !CFG.analytics.plausible_domain) return;
    if (typeof window.plausible === 'function') window.plausible(name, { props: props });
  }

  function pushBeacon(ev) {
    if (!CFG.analytics || !CFG.analytics.beacon_endpoint) return;
    try {
      var body = JSON.stringify(ev);
      if (navigator.sendBeacon) {
        navigator.sendBeacon(CFG.analytics.beacon_endpoint,
          new Blob([body], { type: 'application/json' }));
      }
    } catch (e) { /* falha de telemetria nunca pode quebrar a página */ }
  }

  /* Catálogo de eventos do funil comercial (fonte de referência para auditoria).
     Eventos disparados por clique vêm de data-track no HTML; os demais são
     disparados diretamente aqui. Nenhum evento envia dado pessoal além do que o
     visitante preencheu no formulário de diagnóstico. */
  var EVENT_CATALOG = [
    'page_view',
    'commercial_cta_click',      // qualquer CTA comercial (header, home, plano, rodapé, e-mail)
    'diagnostic_page_view',      // visita à landing /diagnostico/
    'diagnostic_started',        // primeira interação com o formulário
    'diagnostic_submitted',      // lead enviado com sucesso
    'diagnostic_submit_error',   // falha de envio (provider fora)
    'diagnostic_validation_error',
    'briefing_sample_view',      // visita à amostra /briefing-executivo/
    'briefing_print',            // imprimir / salvar PDF da amostra
    'pricing_view',              // visita a /solucoes/ ou clique em preço
    'sector_page_view',          // página/clique setorial (base das páginas P1)
    'high_impact_view',          // página de alto impacto (P1)
    'alert_signup',              // ativação de alertas por e-mail
    'alert_signup_error',
    'demo_request',              // solicitação de demonstração contextualizada
    'whatsapp_click',            // clique em canal de WhatsApp
    'para_empresas_view',        // visita a /para-empresas/
    'lead_bot_blocked'           // honeypot preenchido (envio descartado)
  ];
  window.monitorEventCatalog = EVENT_CATALOG;

  function track(event, props) {
    if (DEBUG && EVENT_CATALOG.indexOf(event) === -1) {
      try { console.warn('[monitor] evento fora do catálogo:', event); } catch (e) { }
    }
    var ev = {
      event: event,
      timestamp: nowIso(),
      page: CFG.page || location.pathname,
      page_kind: CFG.pageKind || '',
      sector: CFG.sector || '',
      title: document.title,
      url: location.href
    };
    var u = utmFlat(UTM);
    Object.keys(u).forEach(function (k) { ev[k] = u[k]; });
    if (props) Object.keys(props).forEach(function (k) { ev[k] = props[k]; });

    pushGtm(ev);
    pushGa4(event, props || {});
    pushPlausible(event, props || {});
    pushBeacon(ev);

    buffer.push(ev);
    if (buffer.length > 200) buffer = buffer.slice(-200);
    safeSet(LS_EVENTS, JSON.stringify(buffer));
    if (DEBUG) {
      try { console.debug('[monitor]', event, ev); } catch (e) { }
    }
    return ev;
  }

  window.monitorTrack = track;

  /* -------------------------------------------------- eventos automáticos -- */
  var KIND_EVENT = {
    pricing: 'pricing_view',
    briefing_sample: 'briefing_sample_view',
    lead_form: 'diagnostic_page_view',
    commercial: 'para_empresas_view'
  };

  track('page_view', { page_kind: CFG.pageKind || '' });
  if (CFG.pageKind && KIND_EVENT[CFG.pageKind]) track(KIND_EVENT[CFG.pageKind], {});

  // Setores / alto impacto (páginas P1 já instrumentadas desde já)
  var sectorPage = document.querySelector('[data-sector-page]');
  if (sectorPage) track('sector_page_view', { sector: sectorPage.getAttribute('data-sector-page') });
  var highImpact = document.querySelector('[data-high-impact-page]');
  if (highImpact) track('high_impact_view', {});

  /* ------------------------------------------------------- clique em CTA --- */
  document.addEventListener('click', function (e) {
    var el = e.target && e.target.closest ? e.target.closest('[data-track]') : null;
    if (!el) return;
    var name = el.getAttribute('data-track');
    var props = {
      cta: el.getAttribute('data-cta') || '',
      destino: el.getAttribute('href') || '',
      texto: (el.textContent || '').trim().slice(0, 120),
      setor: el.getAttribute('data-setor') || '',
      plan: el.getAttribute('data-plan') || ''
    };
    if (name === 'whatsapp_click') props.canal = 'whatsapp';
    track(name, props);
  });

  // Links de WhatsApp sem data-track também entram no funil
  document.addEventListener('click', function (e) {
    var el = e.target && e.target.closest ? e.target.closest('a[href*="wa.me"], a[href*="whatsapp"]') : null;
    if (!el || el.getAttribute('data-track')) return;
    track('whatsapp_click', { destino: el.getAttribute('href') });
  });

  /* ---------------------------------------------------- lead scoring ------- */
  function scoreLead(values) {
    var cfg = CFG.leadScoring || { regras: [], faixas: [], entradas: {} };
    var ent = cfg.entradas || {};
    var hits = [];
    var total = 0;

    function add(id) {
      var regra = (cfg.regras || []).filter(function (r) { return r.id === id; })[0];
      if (!regra) return;
      total += regra.pontos;
      hits.push({ id: id, pontos: regra.pontos, descricao: regra.descricao });
    }
    function has(list, v) { return Array.isArray(list) && v && list.indexOf(v) !== -1; }

    if (has(ent.tamanho_grande, values.tamanho)) add('grande_empresa');
    if (has(ent.tamanho_acima_100, values.tamanho)) add('mais_de_100');
    if (has(ent.setores_prioritarios, values.setor)) add('setor_prioritario');
    if (has(ent.cargos_senior, values.cargo)) add('cargo_decisor');
    if (has(ent.areas_que_pontuam, values.area)) add('area_estruturada');
    if (values.horizonte && values.horizonte === ent.horizonte_imediato) add('preocupacao_imediata');
    if (values.uso_ia && values.uso_ia === ent.uso_ia_critico) add('ia_critica');

    var faixa = (cfg.faixas || []).filter(function (f) { return total >= f.min; })[0] ||
      { classe: 'baixo', rotulo: 'Baixo' };
    return { score: total, classificacao: faixa.classe, rotulo: faixa.rotulo, fatores: hits };
  }

  function formValues(form) {
    var v = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name) return;
      if (el.type === 'checkbox') { v[el.name] = el.checked ? 'sim' : 'nao'; return; }
      if (el.type === 'submit' || el.type === 'button') return;
      v[el.name] = (el.value || '').trim();
    });
    return v;
  }

  function isFreeEmail(email) {
    var dom = (email || '').split('@')[1];
    if (!dom) return false;
    dom = dom.toLowerCase();
    return (CFG.freeEmailDomains || []).indexOf(dom) !== -1;
  }

  /* ------------------------------------------------- envio do lead --------- */
  function buildPayload(form, values, scoring, kind) {
    var p = {};
    Object.keys(values).forEach(function (k) { if (k !== '_gotcha') p[k] = values[k]; });
    p.form_tipo = kind;
    p.lead_score = scoring.score;
    p.lead_classificacao = scoring.classificacao;
    p.lead_classificacao_rotulo = scoring.rotulo;
    p.lead_score_fatores = JSON.stringify(scoring.fatores);
    p.pagina_origem = CFG.page || location.pathname;
    p.url_origem = location.href;
    p.timestamp_envio = nowIso();
    p.utm = JSON.stringify(utmFlat(UTM));
    var u = utmFlat(UTM);
    Object.keys(u).forEach(function (k) { p[k] = u[k]; });
    p._subject = '[Monitor Legislativo IA] ' + (kind === 'alerta' ? 'Alerta regulatório' : 'Diagnóstico') +
      ' — ' + (values.empresa || values.email || 'lead') + ' (score ' + scoring.score + '/' +
      scoring.rotulo + ')';
    return p;
  }

  function saveLeadLocal(payload) {
    var leads = [];
    try { leads = JSON.parse(safeGet(LS_LEADS) || '[]'); } catch (e) { leads = []; }
    leads.push(payload);
    if (leads.length > 50) leads = leads.slice(-50);
    safeSet(LS_LEADS, JSON.stringify(leads));
  }

  function statusEl(form) { return form.querySelector('[data-form-status]'); }
  function setStatus(form, msg, cls) {
    var el = statusEl(form);
    if (!el) return;
    el.textContent = msg;
    el.className = 'form-status ' + (cls || '');
  }

  function mailtoFallback(payload) {
    var linhas = Object.keys(payload).filter(function (k) {
      return k !== '_subject' && payload[k] !== '' && payload[k] != null;
    }).map(function (k) { return k + ': ' + payload[k]; });
    var body = linhas.join('\n');
    var href = 'mailto:' + (CFG.contactEmail || '') +
      '?subject=' + encodeURIComponent(payload._subject || 'Diagnóstico regulatório de IA') +
      '&body=' + encodeURIComponent(body);
    return href;
  }

  function waFallback(payload) {
    if (!CFG.whatsapp) return null;
    var txt = payload._subject + '\n\n' + Object.keys(payload).filter(function (k) {
      return k !== '_subject' && k !== 'lead_score_fatores' && k !== 'utm' && payload[k];
    }).map(function (k) { return k + ': ' + payload[k]; }).join('\n');
    return 'https://wa.me/' + CFG.whatsapp + '?text=' + encodeURIComponent(txt);
  }

  function successPanel(form, payload, scoring, mode) {
    var wrap = form.parentNode;
    var div = document.createElement('div');
    div.className = 'form-ok';
    var resumo = form.getAttribute('data-form') === 'alerta'
      ? 'Pronto. Seu pedido de alerta foi registrado com o recorte informado.'
      : 'Pedido registrado. Você recebe a confirmação e a proposta de diagnóstico no e-mail informado em até 1 dia útil.';
    div.innerHTML = '<h3>Recebido</h3><p>' + resumo + '</p>' +
      '<p class="plan-hint">Protocolo local: <code>' + (payload.timestamp_envio || '') + '</code>' +
      ' · modo de captura: <code>' + mode + '</code>' +
      ' · prioridade interna: <code>' + scoring.rotulo + '</code></p>' +
      '<p class="plan-hint"><a href="' + (CFG.siteUrl || '') + '/briefing-executivo/">Enquanto isso, veja a amostra real do briefing executivo →</a></p>';
    form.style.display = 'none';
    wrap.insertBefore(div, form);
  }

  function submitLead(form, kind) {
    var values = formValues(form);
    var scoring = scoreLead(values);
    var payload = buildPayload(form, values, scoring, kind);
    saveLeadLocal(payload);

    // campos estruturados escondidos (registro do score no próprio envio)
    var set = function (sel, val) {
      var el = form.querySelector(sel);
      if (el) el.value = val == null ? '' : String(val);
    };
    set('[data-lead-score]', scoring.score);
    set('[data-lead-class]', scoring.classificacao + ' (' + scoring.rotulo + ')');
    set('[data-lead-factors]', payload.lead_score_fatores);
    set('[data-lead-payload]', JSON.stringify(payload));
    set('[data-lead-ts]', payload.timestamp_envio);
    set('[data-lead-origin]', payload.pagina_origem);

    if (DEBUG) {
      var dbg = form.querySelector('[data-lead-debug]');
      var out = form.querySelector('[data-lead-debug-out]');
      if (dbg && out) { dbg.hidden = false; out.textContent = JSON.stringify(payload, null, 2); }
      try { console.debug('[monitor] lead', payload); } catch (e) { }
    }

    var eventName = kind === 'alerta' ? 'alert_signup' : 'diagnostic_submitted';

    if (!CFG.leadEndpoint) {
      // Modo fallback: nenhum provider configurado no build.
      var mail = mailtoFallback(payload);
      var wa = waFallback(payload);
      track(eventName, {
        modo: 'fallback', lead_score: scoring.score, lead_class: scoring.classificacao,
        setor: values.setor || '', interesse: values.interesse || ''
      });
      setStatus(form, 'Abrindo seu cliente de e-mail com o pedido preenchido…', '');
      window.location.href = mail;
      if (wa) {
        var extra = document.createElement('p');
        extra.className = 'plan-hint';
        extra.innerHTML = 'Se preferir WhatsApp: <a href="' + wa + '" target="_blank" rel="noopener" data-track="whatsapp_click">enviar por aqui</a>.';
        form.appendChild(extra);
      }
      successPanel(form, payload, scoring, 'fallback-email (provider não configurado)');
      return;
    }

    var btn = form.querySelector('button[type="submit"]');
    if (btn) { btn.disabled = true; btn.textContent = 'Enviando…'; }
    setStatus(form, 'Enviando…', '');

    var done = function (ok) {
      if (btn) { btn.disabled = false; btn.textContent = 'Enviar e solicitar diagnóstico'; }
      if (ok) {
        track(eventName, {
          modo: 'endpoint', provider: CFG.leadProvider || '', lead_score: scoring.score,
          lead_class: scoring.classificacao, setor: values.setor || '',
          interesse: values.interesse || ''
        });
        successPanel(form, payload, scoring, CFG.leadProvider || 'endpoint-http');
      } else {
        setStatus(form, 'Não foi possível enviar agora. Tente novamente ou use o contato direto.', 'err');
        track(kind === 'alerta' ? 'alert_signup_error' : 'diagnostic_submit_error',
          { lead_score: scoring.score, setor: values.setor || '' });
      }
    };

    try {
      fetch(CFG.leadEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify(payload),
        mode: 'cors'
      }).then(function (r) { done(r && r.ok); }).catch(function () {
        // última tentativa: submit nativo para o endpoint do provider
        try {
          form.setAttribute('target', '_blank');
          form.submit();
          track(eventName, { modo: 'native-submit', lead_score: scoring.score });
          done(true);
        } catch (e2) { done(false); }
      });
    } catch (e) { done(false); }
  }

  /* --------------------------------------------------------- formulários --- */
  function bindForm(form) {
    var kind = form.getAttribute('data-form') || 'diagnostico';
    var started = false;

    form.addEventListener('input', function () {
      if (!started) {
        started = true;
        if (kind === 'diagnostico') track('diagnostic_started', { page: CFG.page || '' });
      }
      // aviso de e-mail não corporativo (sem bloquear o envio)
      var emailField = form.querySelector('[name="email"]');
      if (emailField && emailField.value.indexOf('@') > 0) {
        var wrapField = emailField.closest('.field');
        var warn = wrapField ? wrapField.querySelector('.help') : null;
        if (isFreeEmail(emailField.value)) {
          if (warn) {
            warn.innerHTML = 'E-mail de domínio gratuito detectado — o diagnóstico é enviado para ' +
              'endereço corporativo. Se for o único disponível, pode seguir: apenas sinalize a empresa.';
            warn.style.color = 'var(--warn)';
          }
        }
      }
      if (DEBUG) {
        var dbg = form.querySelector('[data-lead-debug]');
        var out = form.querySelector('[data-lead-debug-out]');
        if (dbg && out) {
          var sc = scoreLead(formValues(form));
          dbg.hidden = false;
          out.textContent = 'score ' + sc.score + ' → ' + sc.rotulo + '\n' +
            sc.fatores.map(function (f) { return '+' + f.pontos + ' ' + f.descricao; }).join('\n');
        }
      }
    });

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      // honeypot: envio silencioso de bot é descartado
      var gotcha = form.querySelector('._gotcha, [name="_gotcha"]');
      if (gotcha && gotcha.value) { track('lead_bot_blocked', { form: kind }); return; }

      var ok = true;
      Array.prototype.forEach.call(form.querySelectorAll('.field'), function (f) {
        f.classList.remove('invalid');
        var old = f.querySelector('.err');
        if (old) old.remove();
      });
      Array.prototype.forEach.call(form.elements, function (el) {
        if (!el.required) return;
        var empty = (el.type === 'checkbox') ? !el.checked : !(el.value || '').trim();
        var badEmail = el.type === 'email' && el.value && el.value.indexOf('@') === -1;
        if (empty || badEmail) {
          ok = false;
          var field = el.closest('.field') || el.closest('.consent');
          if (field) {
            field.classList.add('invalid');
            var msg = document.createElement('span');
            msg.className = 'err';
            msg.textContent = badEmail ? 'Informe um e-mail válido.' : 'Campo obrigatório.';
            field.appendChild(msg);
          }
        }
      });
      if (!ok) {
        setStatus(form, 'Revise os campos destacados.', 'err');
        track(kind === 'alerta' ? 'alert_signup_validation_error' : 'diagnostic_validation_error', {});
        return;
      }
      submitLead(form, kind);
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll('[data-form]'), bindForm);

  /* ---------------------------------------------------- prefill por query --- */
  (function prefill() {
    var q = new URLSearchParams(location.search);
    var map = { solucao: 'solucao', interesse: 'interesse', setor: 'setor' };
    Object.keys(map).forEach(function (k) {
      var v = q.get(k);
      if (!v) return;
      Array.prototype.forEach.call(document.querySelectorAll('[data-form]'), function (form) {
        var alvo = form.querySelector('[name="' + map[k] + '"]');
        if (!alvo) return;
        if (alvo.tagName === 'SELECT') {
          var decoded = decodeURIComponent(v).replace(/-/g, ' ');
          var matched = Array.prototype.filter.call(alvo.options, function (o) {
            return o.value.toLowerCase() === v.toLowerCase() ||
              o.value.toLowerCase().indexOf(decoded.toLowerCase()) !== -1;
          })[0];
          if (matched) alvo.value = matched.value;
        } else {
          alvo.value = decodeURIComponent(v);
        }
      });
    });
  })();

  /* ------------------------------------------------------------- diversos --- */
  Array.prototype.forEach.call(document.querySelectorAll('[data-print-brief]'), function (b) {
    b.addEventListener('click', function () {
      track('briefing_print', { page: CFG.page || '' });
      window.print();
    });
  });

  if (DEBUG) {
    try {
      console.debug('[monitor] config comercial', CFG);
      console.debug('[monitor] eventos registrados', buffer);
      console.debug('[monitor] utm', UTM);
    } catch (e) { }
  }
})();
