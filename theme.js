/* theme.js — fælles hjælpere og navigation for RomSniffer.
   Indlæses blokerende i <head> (ca. 3 KB), så side-scripts kan bruge window.RS med det samme.

   Kategorier: sæt live:true på en kategori, når dens sider findes. Så vises kategorivælgeren
   automatisk i toppen (den er skjult, så længe kun én kategori er live). Hver side angiver sin
   kategori med <body data-cat="rom"> (styrer accentfarven i theme.css). */
(function () {
  'use strict';
  var RS = window.RS = {};

  var CATS = [
    { id: 'rom',    label: 'Rom',    href: '/',        live: true  },
    { id: 'whisky', label: 'Whisky', href: '/whisky/', live: false },
    { id: 'gin',    label: 'Gin',    href: '/gin/',    live: false },
    { id: 'cognac', label: 'Cognac', href: '/cognac/', live: false }
  ];
  RS.categories = CATS;

  /* ── Tekst ────────────────────────────────────────────── */
  var ta = null;
  RS.clean = function (s) {            // "Smith &amp;amp; Cross" -> "Smith & Cross"
    ta = ta || document.createElement('textarea');
    var v = String(s == null ? '' : s);
    for (var i = 0; i < 3; i++) { ta.innerHTML = v; var d = ta.value; if (d === v) break; v = d; }
    return v;
  };
  RS.fix = function (s) {              // afkod, og escap til sikker HTML
    return RS.clean(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  };
  RS.plausibleAbv = function (r) {     // samme regler som rom_text.plausible_abv i generatorerne
    var v = Number(r && r.abv);
    if (!v || v < 20) return null;
    if (v >= 70) {
      var n = RS.clean(r.name).toLowerCase().replace(',', '.');
      var re = new RegExp('(^|[^0-9])' + Math.floor(v) + '(\\.[0-9]+)?\\s*%');
      if (!(re.test(n) || n.indexOf('proof') > -1 || n.indexOf('151') > -1)) return null;
    }
    return v;
  };
  RS.fmtAbv = function (v) { return String(Math.round(v * 10) / 10).replace('.', ',') + '%'; };
  RS.thumb = function (url, w) {       // små billeder fra Shopify-CDN (?width=); andre kilder uændret
    if (!url || !/(cdn\.shopify\.com|\/cdn\/shop\/)/.test(url) || /[?&]width=/.test(url)) return url;
    return url + (url.indexOf('?') > -1 ? '&' : '?') + 'width=' + w;
  };

  /* ── Ikoner (tynde linjer; farven følger teksten) ─────── */
  RS.HEART_SVG  = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/></svg>';
  RS.GLASS_SVG  = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 22h8"/><path d="M7 10h10"/><path d="M12 15v7"/><path d="M12 15a5 5 0 0 0 5-5c0-2-.5-4-2-8H9c-1.5 4-2 6-2 8a5 5 0 0 0 5 5Z"/></svg>';
  RS.SEARCH_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>';

  /* ── Navigation: mobilmenu + kategorivælger ───────────── */
  function init() {
    var nav = document.querySelector('nav');
    if (!nav) return;
    var cat = document.body.getAttribute('data-cat') || 'rom';

    var links = nav.querySelector('.nav-links');
    if (links && !nav.querySelector('.nav-toggle')) {
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'nav-toggle';
      b.setAttribute('aria-label', 'Menu'); b.setAttribute('aria-expanded', 'false');
      b.innerHTML = '<span></span><span></span><span></span>';
      nav.insertBefore(b, links);
      b.addEventListener('click', function () {
        var open = nav.classList.toggle('nav-open');
        b.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
      links.addEventListener('click', function (e) { if (e.target.closest('a')) nav.classList.remove('nav-open'); });
      document.addEventListener('keydown', function (e) { if (e.key === 'Escape') nav.classList.remove('nav-open'); });
    }

    var live = CATS.filter(function (c) { return c.live; });
    var logo = nav.querySelector('.nav-logo');
    if (live.length > 1 && logo && !nav.querySelector('.cat-switch')) {
      var s = document.createElement('div');
      s.className = 'cat-switch'; s.setAttribute('role', 'navigation'); s.setAttribute('aria-label', 'Kategorier');
      s.innerHTML = live.map(function (c) {
        return '<a href="' + c.href + '"' + (c.id === cat ? ' class="active" aria-current="page"' : '') + '>' + c.label + '</a>';
      }).join('');
      logo.parentNode.insertBefore(s, logo.nextSibling);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
