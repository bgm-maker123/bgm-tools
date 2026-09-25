// BGM投稿記録ページ
// data.json を読み込んで表示するだけのシンプルなプログラムです。

(function () {
  'use strict';

  // GitHub のリポジトリ（「データを編集」ボタンの行き先。自動で判定できないとき用）
  var FALLBACK_REPO = 'bgm-maker123/bgm-tools';
  var BRANCH = 'main';

  var state = { data: null, metric: 'total', sort: 'date' };

  function $(id) { return document.getElementById(id); }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }

  // "12,345" や "45.2%" や全角数字も数値にする。空欄は null
  function toNum(v) {
    if (typeof v === 'number') return isFinite(v) ? v : null;
    if (v === null || v === undefined) return null;
    var s = String(v).replace(/[０-９．]/g, function (c) {
      return c === '．' ? '.' : String.fromCharCode(c.charCodeAt(0) - 0xFEE0);
    }).replace(/[,，%％\s]/g, '');
    if (s === '') return null;
    var n = Number(s);
    return isFinite(n) ? n : null;
  }

  function fmtInt(n) { return n === null ? '–' : Math.round(n).toLocaleString('ja-JP'); }
  function fmtPct(n) { return n === null ? '–' : (Math.round(n * 10) / 10) + '%'; }

  function dateKey(s) {
    var m = String(s || '').match(/(\d{4})\D(\d{1,2})\D(\d{1,2})/);
    if (!m) return '';
    return m[1] + '-' + ('0' + m[2]).slice(-2) + '-' + ('0' + m[3]).slice(-2);
  }

  function safeUrl(u) {
    u = String(u || '').trim();
    return /^https?:\/\//i.test(u) ? u : null;
  }

  function avg(list) {
    if (!list.length) return null;
    var t = 0;
    list.forEach(function (x) { t += x; });
    return t / list.length;
  }

  // ---------- 読み込み ----------
  function load() {
    fetch('data.json?t=' + Date.now(), { cache: 'no-store' })
      .then(function (r) {
        if (!r.ok) throw new Error('data.json を読み込めませんでした（' + r.status + '）');
        return r.text();
      })
      .then(function (text) {
        var data;
        try {
          data = JSON.parse(text);
        } catch (e) {
          throw new Error(jsonErrorMessage(text, e));
        }
        state.data = normalize(data);
        render();
      })
      .catch(function (e) {
        var box = $('error');
        box.hidden = false;
        box.textContent = e.message +
          (location.protocol === 'file:' ? '\n\n※ パソコンで index.html を直接開くと表示されません。GitHub Pages のURLで開いてください。' : '');
      });
  }

  function jsonErrorMessage(text, e) {
    var msg = 'data.json の書き方に間違いがあります。';
    var m = String(e.message).match(/position (\d+)/);
    var line = null;
    var lm = String(e.message).match(/line (\d+)/);
    if (lm) line = Number(lm[1]);
    else if (m) line = text.slice(0, Number(m[1])).split('\n').length;
    if (line) msg += '\n→ ' + line + ' 行目あたりを確認してください。';
    msg += '\n\nよくある原因:\n・「}」と「{」の間のカンマ（,）が足りない\n・最後の項目の後ろに余計なカンマがある\n・「"」が片方だけになっている';
    msg += '\n\n（詳細: ' + e.message + '）';
    return msg;
  }

  function normalize(d) {
    d = d || {};
    return {
      channelName: d.channelName || 'BGM投稿記録',
      videos: (Array.isArray(d.videos) ? d.videos : []).map(function (v, i) {
        v = v || {};
        return {
          index: i,
          date: String(v.date || '').trim(),
          dateKey: dateKey(v.date),
          theme: String(v.theme || '').trim() || '（テーマ未入力）',
          title: String(v.title || '').trim(),
          fullUrl: safeUrl(v.fullUrl),
          shortUrl: safeUrl(v.shortUrl),
          views: toNum(v.views),
          retention: toNum(v.retention),
          memo: String(v.memo || '').trim()
        };
      }),
      nextThemes: Array.isArray(d.nextThemes) ? d.nextThemes : [],
      sunoPrompts: Array.isArray(d.sunoPrompts) ? d.sunoPrompts : []
    };
  }

  // ---------- 表示 ----------
  function render() {
    var d = state.data;
    document.title = d.channelName;
    $('channel-name').textContent = d.channelName;
    renderStats(d.videos);
    renderChart(d.videos);
    renderVideos(d.videos);
    renderThemes(d.nextThemes);
    renderPrompts(d.sunoPrompts);
  }

  function renderStats(videos) {
    var views = videos.map(function (v) { return v.views; }).filter(function (n) { return n !== null; });
    var rets = videos.map(function (v) { return v.retention; }).filter(function (n) { return n !== null; });
    $('stat-count').textContent = videos.length + '本';
    $('stat-views').textContent = views.length ? fmtInt(views.reduce(function (a, b) { return a + b; }, 0)) : '–';
    $('stat-ret').textContent = fmtPct(avg(rets));
  }

  function themeGroups(videos) {
    var map = {};
    var order = [];
    videos.forEach(function (v) {
      if (!map[v.theme]) { map[v.theme] = { theme: v.theme, count: 0, views: [], rets: [] }; order.push(v.theme); }
      var g = map[v.theme];
      g.count++;
      if (v.views !== null) g.views.push(v.views);
      if (v.retention !== null) g.rets.push(v.retention);
    });
    return order.map(function (k) {
      var g = map[k];
      g.total = g.views.length ? g.views.reduce(function (a, b) { return a + b; }, 0) : null;
      g.avg = avg(g.views);
      g.ret = avg(g.rets);
      return g;
    });
  }

  function renderChart(videos) {
    var box = $('chart');
    box.innerHTML = '';
    var groups = themeGroups(videos);
    if (!groups.length) { box.appendChild(el('p', 'empty', 'まだ動画が登録されていません。')); return; }

    var metric = state.metric;
    var val = function (g) { return g[metric]; };
    groups.sort(function (a, b) {
      var x = val(a), y = val(b);
      if (x === null && y === null) return 0;
      if (x === null) return 1;
      if (y === null) return -1;
      return y - x;
    });
    var max = 0;
    groups.forEach(function (g) { if (val(g) !== null && val(g) > max) max = val(g); });
    if (metric === 'ret') max = Math.max(max, 1);

    var anyData = groups.some(function (g) { return val(g) !== null; });
    if (!anyData) {
      box.appendChild(el('p', 'empty', (metric === 'ret' ? '視聴維持率' : '再生数') + 'を data.json に入力すると、ここにグラフが出ます。'));
    }

    groups.forEach(function (g) {
      var v = val(g);
      var row = el('div', 'bar-row');
      row.tabIndex = 0;
      row.appendChild(el('span', 'bar-label', g.theme));
      var area = el('div', 'bar-area');
      var bar = el('div', 'bar');
      bar.style.width = v === null || max === 0 ? '0' : Math.max(1, (v / max) * 80) + '%';
      if (v === null) bar.style.display = 'none';
      area.appendChild(bar);
      var label = v === null ? '未入力' : (metric === 'ret' ? fmtPct(v) : fmtInt(v));
      area.appendChild(el('span', 'bar-value', label + '（' + g.count + '本）'));
      row.appendChild(area);

      var tipText = g.theme + '\n動画 ' + g.count + '本\n合計再生数 ' + fmtInt(g.total) +
        '\n平均再生数 ' + fmtInt(g.avg) + '\n平均維持率 ' + fmtPct(g.ret);
      bindTip(row, tipText);
      box.appendChild(row);
    });
  }

  function bindTip(node, text) {
    var tip = $('tip');
    function show(x, y) {
      tip.textContent = '';
      text.split('\n').forEach(function (line, i) {
        if (i) tip.appendChild(document.createElement('br'));
        tip.appendChild(document.createTextNode(line));
      });
      tip.hidden = false;
      var w = tip.offsetWidth, h = tip.offsetHeight;
      var left = Math.min(Math.max(8, x + 12), window.innerWidth - w - 8);
      var top = y - h - 12 < 8 ? y + 16 : y - h - 12;
      tip.style.left = left + 'px';
      tip.style.top = top + 'px';
    }
    function hide() { tip.hidden = true; }
    node.addEventListener('mousemove', function (e) { show(e.clientX, e.clientY); });
    node.addEventListener('mouseleave', hide);
    node.addEventListener('focus', function () {
      var r = node.getBoundingClientRect();
      show(r.left + r.width / 2, r.top);
    });
    node.addEventListener('blur', hide);
    node.addEventListener('touchstart', function (e) {
      var t = e.touches[0];
      show(t.clientX, t.clientY);
    }, { passive: true });
    window.addEventListener('scroll', hide, { passive: true });
  }

  function renderVideos(videos) {
    var box = $('videos');
    box.innerHTML = '';
    var list = videos.slice();
    var nullsLast = function (a, b) {
      if (a === null && b === null) return 0;
      if (a === null) return 1;
      if (b === null) return -1;
      return b - a;
    };
    if (state.sort === 'views') list.sort(function (a, b) { return nullsLast(a.views, b.views) || b.index - a.index; });
    else if (state.sort === 'retention') list.sort(function (a, b) { return nullsLast(a.retention, b.retention) || b.index - a.index; });
    else list.sort(function (a, b) {
      if (a.dateKey !== b.dateKey) {
        if (!a.dateKey) return 1;
        if (!b.dateKey) return -1;
        return a.dateKey < b.dateKey ? 1 : -1;
      }
      return b.index - a.index;
    });

    if (!list.length) { box.appendChild(el('p', 'empty', 'まだ動画が登録されていません。')); return; }

    list.forEach(function (v) {
      var card = el('article', 'video');
      var top = el('div', 'video-top');
      top.appendChild(el('h3', 'video-title', v.title || v.theme));
      top.appendChild(el('span', 'video-date', v.date || '日付未入力'));
      card.appendChild(top);
      card.appendChild(el('span', 'chip', v.theme));

      var nums = el('div', 'nums');
      var n1 = el('span', null, '再生数 ');
      n1.appendChild(el('b', v.views === null ? 'muted' : null, fmtInt(v.views)));
      var n2 = el('span', null, '維持率 ');
      n2.appendChild(el('b', v.retention === null ? 'muted' : null, fmtPct(v.retention)));
      nums.appendChild(n1);
      nums.appendChild(n2);
      card.appendChild(nums);

      if (v.fullUrl || v.shortUrl) {
        var links = el('div', 'links');
        [[v.fullUrl, '▶ フル動画'], [v.shortUrl, '▶ ショート']].forEach(function (p) {
          if (!p[0]) return;
          var a = el('a', null, p[1]);
          a.href = p[0];
          a.target = '_blank';
          a.rel = 'noopener';
          links.appendChild(a);
        });
        card.appendChild(links);
      }
      if (v.memo) card.appendChild(el('p', 'memo', v.memo));
      box.appendChild(card);
    });
  }

  function renderThemes(themes) {
    var ul = $('themes');
    ul.innerHTML = '';
    if (!themes.length) { ul.appendChild(el('li', 'empty', 'まだありません。data.json の nextThemes に追加できます。')); return; }
    themes.forEach(function (t) {
      if (typeof t === 'string') t = { theme: t };
      t = t || {};
      var li = el('li', null, String(t.theme || ''));
      if (t.memo) li.appendChild(el('span', 'sub', String(t.memo)));
      ul.appendChild(li);
    });
  }

  function renderPrompts(prompts) {
    var box = $('prompts');
    box.innerHTML = '';
    if (!prompts.length) { box.appendChild(el('p', 'empty', 'まだありません。data.json の sunoPrompts に追加できます。')); return; }
    prompts.forEach(function (p) {
      if (typeof p === 'string') p = { prompt: p };
      p = p || {};
      var card = el('div', 'prompt');
      var head = el('div', 'prompt-head');
      head.appendChild(el('p', 'prompt-name', String(p.name || 'プロンプト')));
      var text = String(p.prompt || '');
      if (text) {
        var btn = el('button', 'btn', 'コピー');
        btn.type = 'button';
        btn.addEventListener('click', function () { copy(text, btn); });
        head.appendChild(btn);
      }
      card.appendChild(head);
      if (text) card.appendChild(el('pre', null, text));
      if (p.memo) card.appendChild(el('p', 'memo', String(p.memo)));
      box.appendChild(card);
    });
  }

  function copy(text, btn) {
    var done = function () { btn.textContent = 'コピーしました'; setTimeout(function () { btn.textContent = 'コピー'; }, 1500); };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
    } else { fallbackCopy(text); done(); }
  }
  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) { /* 何もしない */ }
    document.body.removeChild(ta);
  }

  // ---------- 編集リンク ----------
  function setupEditLink() {
    var repo = FALLBACK_REPO;
    var host = location.hostname.match(/^([^.]+)\.github\.io$/i);
    var first = location.pathname.split('/').filter(Boolean)[0];
    if (host && first && first !== 'index.html') repo = host[1] + '/' + first;
    $('edit-link').href = 'https://github.com/' + repo + '/edit/' + BRANCH + '/docs/data.json';
  }

  // ---------- ダークモード切り替え（自動 → ライト → ダーク） ----------
  var THEME_KEY = 'bgm-log-theme';
  var THEME_LABEL = { auto: '🌓 自動', light: '☀️ ライト', dark: '🌙 ダーク' };
  function getTheme() {
    try { return localStorage.getItem(THEME_KEY) || 'auto'; } catch (e) { return 'auto'; }
  }
  function applyTheme(t) {
    if (t === 'auto') document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', t);
    $('theme-toggle').textContent = THEME_LABEL[t] || THEME_LABEL.auto;
  }
  function setupTheme() {
    var t = getTheme();
    applyTheme(t);
    $('theme-toggle').addEventListener('click', function () {
      t = t === 'auto' ? 'light' : t === 'light' ? 'dark' : 'auto';
      try { localStorage.setItem(THEME_KEY, t); } catch (e) { /* 保存できなくてもOK */ }
      applyTheme(t);
    });
  }

  // ---------- 操作 ----------
  function setupControls() {
    $('sort').addEventListener('change', function (e) {
      state.sort = e.target.value;
      if (state.data) renderVideos(state.data.videos);
    });
    Array.prototype.forEach.call(document.querySelectorAll('.seg button'), function (b) {
      b.addEventListener('click', function () {
        state.metric = b.getAttribute('data-metric');
        Array.prototype.forEach.call(document.querySelectorAll('.seg button'), function (x) {
          x.classList.toggle('on', x === b);
        });
        if (state.data) renderChart(state.data.videos);
      });
    });
  }

  setupTheme();
  setupEditLink();
  setupControls();
  load();
})();
