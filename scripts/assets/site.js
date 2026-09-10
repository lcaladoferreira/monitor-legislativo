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
    var score = controls.score ? parseInt(controls.score.value, 10) : 0;
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
