// Filtros client-side da lista de proposições
(function () {
  var rows = Array.prototype.slice.call(document.querySelectorAll('[data-prop]'));
  var controls = {
    q: document.getElementById('f-q'),
    casa: document.getElementById('f-casa'),
    ano: document.getElementById('f-ano'),
    status: document.getElementById('f-status'),
    cat: document.getElementById('f-cat'),
    score: document.getElementById('f-score')
  };
  if (!rows.length || !controls.q) return;
  var count = document.getElementById('count');

  function apply() {
    var q = controls.q.value.trim().toLowerCase();
    var casa = controls.casa ? controls.casa.value : '';
    var ano = controls.ano ? controls.ano.value : '';
    var status = controls.status ? controls.status.value : '';
    var cat = controls.cat ? controls.cat.value : '';
    var scoreValue = controls.score ? controls.score.value : '0';
    var score = parseInt(scoreValue, 10) || 0;
    var visible = 0;
    rows.forEach(function (r) {
      var d = r.dataset;
      var ok = true;
      if (q && (d.search.indexOf(q) === -1)) ok = false;
      if (casa && d.casa !== casa) ok = false;
      if (ano && d.ano !== ano) ok = false;
      if (status && d.statusgroup !== status) ok = false;
      if (cat && d.cats.indexOf(',' + cat + ',') === -1) ok = false;
      if (score && parseInt(d.score, 10) < score) ok = false;
      if (scoreValue === '60-79' && parseInt(d.score, 10) > 79) ok = false;
      if (scoreValue === 'low' && parseInt(d.score, 10) >= 60) ok = false;
      r.style.display = ok ? '' : 'none';
      if (ok) visible++;
    });
    if (count) count.textContent = visible + ' de ' + rows.length + ' proposições';
  }
  Object.keys(controls).forEach(function (k) {
    if (controls[k]) controls[k].addEventListener('input', apply);
    if (controls[k]) controls[k].addEventListener('change', apply);
  });
  apply();
})();

// Filtro por período da página de atualizações (preserva o filtro de proposições acima)
(function () {
  var items = Array.prototype.slice.call(document.querySelectorAll('[data-update]'));
  var btns = Array.prototype.slice.call(document.querySelectorAll('[data-ufilter]'));
  if (!items.length || !btns.length) return;
  var count = document.getElementById('u-count');
  function apply(limit) {
    var visible = 0;
    items.forEach(function (el) {
      var d = parseInt(el.getAttribute('data-days'), 10);
      var ok = (limit === 'all') || (!isNaN(d) && d <= parseInt(limit, 10));
      el.style.display = ok ? '' : 'none';
      if (ok) visible++;
    });
    if (count) count.textContent = visible + ' de ' + items.length + ' atualizações';
    btns.forEach(function (b) {
      if (b.getAttribute('data-ufilter') === String(limit)) b.classList.add('active');
      else b.classList.remove('active');
    });
  }
  btns.forEach(function (b) {
    b.addEventListener('click', function () { apply(b.getAttribute('data-ufilter')); });
  });
  apply('7');
})();

// Frescor do monitoramento (selo no topo de todas as páginas, cartões de idade e
// alertas do painel). Recalcula no navegador a idade da última execução: se o
// cron parar, o próprio site avisa o visitante mesmo sem rebuild.
//
// Os limiares NÃO são fixados aqui: o build os deriva do agendamento real
// (scripts/frescor.py) e os entrega em data-fresh-ok / data-fresh-warn. A
// versão anterior trazia limites fixos pensados para quatro coletas diárias e
// descrevia um agendamento que já não existia — com o cron horário, um dataset
// 23 h parado continuava classificado como "em dia".
(function () {
  var CORES = { ok: 'green', atencao: 'yellow', critico: 'red' };

  function num(el, attr, padrao) {
    var v = parseFloat(el.getAttribute(attr));
    return isNaN(v) ? padrao : v;
  }

  function estadoHoras(h, ok, warn) {
    if (h === null || isNaN(h)) return 'atencao';
    if (h <= ok) return 'ok';
    if (h <= warn) return 'atencao';
    return 'critico';
  }

  function rel(h) {
    if (h === null || isNaN(h)) return 'idade desconhecida';
    if (h < 1) return 'há ' + Math.round(h * 60) + ' min';
    if (h < 48) return 'há ' + h.toFixed(h < 10 ? 1 : 0) + ' h';
    return 'há ' + Math.round(h / 24) + ' dias';
  }

  // Mesmo formato de `_idade_txt` no build, para número e texto não divergirem.
  function idadeTxt(h) {
    if (h === null || isNaN(h)) return '—';
    return h < 48 ? h.toFixed(1) + ' h' : (h / 24).toFixed(1) + ' dias';
  }

  function idadeDe(el, attr) {
    var ts = Date.parse(el.getAttribute(attr) || '');
    return isNaN(ts) ? null : (Date.now() - ts) / 3600000;
  }

  // --- selo do cabeçalho
  var badges = Array.prototype.slice.call(document.querySelectorAll('[data-freshness]'));
  badges.forEach(function (b) {
    var h = idadeDe(b, 'data-freshness');
    if (h === null) return;
    var ok = num(b, 'data-fresh-ok', 3);
    var warn = num(b, 'data-fresh-warn', 8);
    var estado = estadoHoras(h, ok, warn);
    b.setAttribute('data-estado', estado);
    var lbl = b.querySelector('[data-fresh-label]');
    if (lbl) {
      lbl.textContent = 'Última verificação: ' + rel(h) +
        (estado === 'critico' ? ' · verifique o cron' : '');
      b.title = 'Última verificação registrada: ' +
        (b.getAttribute('data-fresh-abs') || '') + ' (' + rel(h) + ')';
    }
  });

  // --- cartões de idade (home e /monitoramento/): o valor impresso no build
  // envelhece a cada minuto; aqui ele é corrigido para a hora real da visita.
  Array.prototype.slice.call(document.querySelectorAll('[data-age-from]'))
    .forEach(function (c) {
      var h = idadeDe(c, 'data-age-from');
      if (h === null) return;
      var estado = estadoHoras(h, num(c, 'data-age-ok', 3), num(c, 'data-age-warn', 8));
      c.setAttribute('data-age-estado', estado);
      var numEl = c.querySelector('[data-age-num]');
      if (numEl) numEl.textContent = idadeTxt(h);
      Object.keys(CORES).forEach(function (k) { c.classList.remove(k); });
      if (CORES[estado]) c.classList.add(CORES[estado]);
    });

  // --- faixa de aviso no painel quando a execução está velha
  var painel = document.querySelector('[data-freshness-panel]');
  if (painel && !painel.querySelector('[data-fresh-aviso]')) {
    var h2 = idadeDe(painel, 'data-freshness-panel');
    if (h2 !== null) {
      var ok2 = num(painel, 'data-fresh-ok', 3);
      var warn2 = num(painel, 'data-fresh-warn', 8);
      var estado2 = estadoHoras(h2, ok2, warn2);
      if (estado2 !== 'ok') {
        var cron = painel.getAttribute('data-fresh-cron') || 'conforme o agendamento do repositório';
        var aviso = document.createElement('div');
        aviso.className = 'alert ' + (estado2 === 'critico' ? 'critico' : 'atencao');
        aviso.setAttribute('data-fresh-aviso', estado2);
        aviso.innerHTML = '<b>Painel visto ' + rel(h2) + ' depois da última execução registrada.</b>' +
          '<span>A coleta está agendada ' + cron + ' (limite: ' + warn2 +
          ' h). Ou o cron parou, ou a execução falhou antes do commit e nada foi ' +
          'publicado — verifique a aba Actions do repositório.</span>';
        painel.parentNode.insertBefore(aviso, painel);
      }
    }
  }
})();
