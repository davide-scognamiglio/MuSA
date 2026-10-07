// MuSA site. Motion follows the 1.4 film: things arrive, hold, and move only when the data changes.
// The page is complete without this file. It adds the `js` class (which arms the CSS motion states)
// and plays each moment once. With reduced motion, everything is shown in its final state.
(() => {
  "use strict";
  const root = document.documentElement;
  root.classList.add("js");
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const fmt = (n) => Math.round(n).toLocaleString("en-US");
  const later = (ms, f) => setTimeout(f, reduce ? 0 : ms);

  // Plays `fn` once, when `el` is well inside the viewport.
  const once = (els, fn, threshold = 0.35) => {
    if (!("IntersectionObserver" in window)) { els.forEach(fn); return; }
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting) { fn(e.target); io.unobserve(e.target); }
    }), { threshold });
    els.forEach((el) => io.observe(el));
  };

  // ── Navigation (mobile) ──
  const nav = $(".nav"), menu = $(".menu-btn");
  if (menu) menu.addEventListener("click", () => menu.setAttribute("aria-expanded", String(nav.classList.toggle("open"))));

  // ── Back to top: appears after about two screens of scrolling ──
  const top = $(".totop");
  if (top) {
    const toggle = () => top.classList.toggle("show", window.scrollY > window.innerHeight * 2);
    addEventListener("scroll", () => requestAnimationFrame(toggle), { passive: true });
    toggle();
    top.addEventListener("click", (e) => {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
      const brand = $(".brand");                  // keep keyboard focus at the top too
      if (brand) brand.focus({ preventScroll: true });
    });
  }

  // ── Copy buttons: copy the sibling <code>, or the element named in data-copy ──
  $$(".copy").forEach((b) => b.addEventListener("click", async () => {
    const src = b.dataset.copy ? $(b.dataset.copy) : b.parentElement.querySelector("code");
    try {
      await navigator.clipboard.writeText(src.textContent.trim());
      const t = b.textContent; b.textContent = "Copied"; setTimeout(() => (b.textContent = t), 1400);
    } catch (e) { /* clipboard blocked: the text stays selectable */ }
  }));

  // ── Film: no audio. Plays on screen on wide screens; on phones and data saver it waits for Play ──
  const v = $("#filmv"), bPlay = $("#filmplay");
  if (v) {
    const sync = () => { bPlay.textContent = v.paused ? "Play" : "Pause"; bPlay.setAttribute("aria-pressed", String(!v.paused)); };
    let userPaused = false;
    bPlay.addEventListener("click", () => { if (v.paused) { userPaused = false; v.play(); } else { userPaused = true; v.pause(); } });
    ["play", "pause"].forEach((ev) => v.addEventListener(ev, sync));
    const saveData = navigator.connection && navigator.connection.saveData;
    const auto = !reduce && !saveData && window.matchMedia("(min-width: 761px)").matches;
    if (auto && "IntersectionObserver" in window) {
      new IntersectionObserver(([e]) => {
        if (e.isIntersecting && !userPaused) { v.preload = "auto"; v.play().catch(() => {}); }
        else if (!e.isIntersecting) v.pause();
      }, { threshold: 0.45 }).observe(v);
    }
    sync();
  }

  // ── Story: 22,572 → phenotype → 1 → the card (film scenes 1–4) ──
  const story = $("#story");
  if (story) {
    const count = $("#count"), label = $("#countlabel"), steps = $$("[data-at]", story);
    const show = (p) => {
      steps.forEach((s) => s.classList.toggle("on", p >= +s.dataset.at));
      const t = clamp((p - 0.44) / 0.18), e = 1 - Math.pow(1 - t, 3);
      count.textContent = t >= 1 ? "1" : fmt(22572 - 22571 * e);
      label.textContent = t >= 1 ? "variant in the review set" : p >= 0.18 ? "variants, against the patient's phenotype" : "variants in one exome";
    };
    if (reduce) {
      show(1); story.classList.add("done");
    } else if (window.matchMedia("(min-width: 1100px)").matches) {
      // Wide screens: the stage sticks and the scroll position drives it.
      story.classList.add("scrolled");
      const draw = () => {
        const r = story.getBoundingClientRect(), h = r.height - window.innerHeight;
        show(clamp(-r.top / Math.max(1, h)));
      };
      addEventListener("scroll", () => requestAnimationFrame(draw), { passive: true });
      draw();
    } else {
      // Phones and tablets: the same sequence plays once, on a clock, when it comes into view.
      show(0);
      once([count], () => {
        const t0 = performance.now(), dur = 5200;
        const tick = (t) => { const p = clamp((t - t0) / dur); show(p); if (p < 1) requestAnimationFrame(tick); else story.classList.add("done"); };
        requestAnimationFrame(tick);
      }, 0.6);
    }
  }

  // ── Pipeline map: drawn left to right as it crosses the viewport (film scene 5) ──
  const mapbox = $("#mapbox"), svg = mapbox && $("svg", mapbox);
  if (svg && !reduce && window.matchMedia("(min-width: 901px)").matches) {
    const W = svg.viewBox.baseVal.width || 1795;
    const lines = $$("path[data-x0]", svg).map((el) => {
      const len = el.getTotalLength();
      el.style.strokeDasharray = `${len} ${len}`;
      return { el, x0: +el.dataset.x0, x1: +el.dataset.x1, len };
    });
    const lineSet = new Set(lines.map((l) => l.el));
    const parts = Array.from(svg.children).filter((el) => !lineSet.has(el) && !/^(style|defs|title|desc)$/i.test(el.tagName))
      .map((el) => { let x = 0; try { x = el.getBBox().x; } catch (e) {} el.style.transition = "opacity .5s"; return { el, x }; });
    const draw = () => {
      const r = mapbox.getBoundingClientRect(), vh = window.innerHeight;
      const p = clamp((vh * 0.85 - r.top) / (vh * 0.55));   // starts at 85% of the viewport, done at 30%
      const X = p * (W + 40) - 20;
      lines.forEach((l) => {
        const f = clamp((X - l.x0) / Math.max(1, l.x1 - l.x0));
        l.el.style.strokeDashoffset = String(l.len * (1 - f));
        l.el.style.opacity = f > 0 ? "1" : "0";
      });
      parts.forEach((q) => (q.el.style.opacity = X >= q.x ? "1" : "0"));
    };
    addEventListener("scroll", () => requestAnimationFrame(draw), { passive: true });
    addEventListener("resize", draw);
    draw();
  }
  // Narrow screens: the vertical stage list, one stage after another.
  const stages = $("#stages");
  if (stages) {
    $$("li", stages).forEach((li, i) => (li.style.transitionDelay = `${i * 0.14}s`));
    once([stages], (el) => el.classList.add("in"), 0.2);
  }

  // ── Two outputs: the report drifts, MAF rows arrive one by one (film scene 7) ──
  once($$("#reportframe"), (el) => el.classList.add("in"), 0.4);
  $$("#mafframe tbody tr").forEach((tr, i) => (tr.style.transitionDelay = `${0.2 + i * 0.16}s`));
  once($$("#mafframe"), (el) => {
    el.classList.add("in");
    const sc = $(".maf-scroll", el);   // then glide once through the columns, as in the film
    if (!reduce && sc.scrollWidth > sc.clientWidth) later(1700, () => sc.scrollTo({ left: sc.scrollWidth, behavior: "smooth" }));
  }, 0.5);

  // ── Sources converge into one row (film scene 6) ──
  const NAMES = [
    ["Ensembl VEP", 1], ["ClinVar", 1], ["gnomAD 4.1", 1], ["dbNSFP 5.3", 1], ["AlphaMissense", 1],
    ["CADD", 0], ["REVEL", 0], ["SpliceAI", 0], ["ClinGen", 0], ["OMIM", 0],
    ["Orphanet", 0], ["HPO", 0], ["GenCC", 0], ["MANE Select", 0], ["EVE", 0],
    ["PrimateAI", 0], ["ESM1b", 0], ["MaveDB", 0], ["ProtVar", 0], ["RENOVO 1.5", 0],
  ];
  const conv = $("#converge"), row = $("#row");
  if (conv && row) {
    for (let i = 0; i < 50; i++) row.appendChild(document.createElement("i"));
    const cells = $$("i", row);
    const cols = window.matchMedia("(max-width: 760px)").matches ? 2 : 5, rows = Math.ceil(NAMES.length / cols);
    const nodes = NAMES.map(([t, key], i) => {
      const d = document.createElement("span");
      d.className = "nm" + (key ? " key" : ""); d.textContent = t;
      const c = i % cols, r = Math.floor(i / cols);
      d.style.left = `${(c + 0.5 + (r % 2 ? 0.16 : -0.16)) / cols * 100}%`;
      d.style.top = `${(r + 0.5) / rows * 100}%`;
      d.style.translate = "-50% -50%";
      conv.appendChild(d);
      return d;
    });
    const fill = () => {
      cells.forEach((c, i) => later(i * 22, () => c.classList.add("on")));
      later(cells.length * 22 + 100, () => row.classList.add("done"));
    };
    if (reduce) { conv.classList.add("go"); fill(); }
    else once([conv], () => later(700, () => {
      const rr = row.getBoundingClientRect();
      nodes.forEach((d, i) => {
        const b = d.getBoundingClientRect();
        const tx = rr.left + rr.width * ((i + 0.5) / nodes.length) - (b.left + b.width / 2);
        const ty = rr.top + rr.height / 2 - (b.top + b.height / 2);
        d.style.transitionDelay = `${(i % 5) * 0.06 + Math.floor(i / 5) * 0.05}s`;
        d.style.transform = `translate(${tx}px, ${ty}px) scale(.35)`;
      });
      conv.classList.add("go");
      later(1100, fill);
    }), 0.6);
  }
})();
