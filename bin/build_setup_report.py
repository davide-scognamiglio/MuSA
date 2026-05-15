#!/usr/bin/env python3
import sys
import datetime
import base64
import os

# ══════════════════════════════════════════════════════════════════════════════
#  THEME — edit freely, all colours and fonts live here
# ══════════════════════════════════════════════════════════════════════════════
THEME = {
    # backgrounds
    "bg":           "#0b0d14",
    "surface":      "#121520",
    "surface2":     "#1a1f2e",

    # borders
    "border":       "#2a2f42",
    "border2":      "#4a5070",   # ← brighter so labels/dividers are visible

    # text
    "text":         "#e6e8f2",
    "muted":        "#9aa0b8",   # clearly readable on dark surfaces

    # semantic colours
    "ok":           "#3aad82",   # slightly brighter teal for dark bg legibility
    "ok_dim":       "#3aad821a",
    "ok_border":    "#3aad8255",

    "fail":         "#d94f5c",   # brighter crimson — readable on dark
    "fail_dim":     "#d94f5c15",
    "fail_border":  "#d94f5c55",

    "pend":         "#d4a43a",   # warm gold — readable on dark
    "pend_dim":     "#d4a43a15",
    "pend_border":  "#d4a43a55",

    "accent":       "#6c5fff",   # indigo-violet

    # typography
    "font_display": "'Poppins', sans-serif",
    "font_body":    "'Poppins', sans-serif",
    "font_mono":    "'DM Mono', 'Courier New', monospace",
    "google_fonts": "https://fonts.googleapis.com/css2?family=Poppins:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400&family=DM+Mono:wght@400;500&display=swap",

    # shape
    "radius": "8px",
}


def css_vars(t):
    mapping = {
        "bg":           "bg",
        "surface":      "surface",
        "surface2":     "surface2",
        "border":       "border",
        "border2":      "border2",
        "text":         "text",
        "muted":        "muted",
        "ok":           "ok",
        "ok_dim":       "ok-dim",
        "ok_border":    "ok-border",
        "fail":         "fail",
        "fail_dim":     "fail-dim",
        "fail_border":  "fail-border",
        "pend":         "pend",
        "pend_dim":     "pend-dim",
        "pend_border":  "pend-border",
        "accent":       "accent",
        "font_display": "font-display",
        "font_body":    "font-body",
        "font_mono":    "font-mono",
        "radius":       "radius",
    }
    lines = ["  :root {"]
    for key, css_name in mapping.items():
        lines.append(f"    --{css_name}: {t[key]};")
    lines.append("  }")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════

def load_logo_base64(logo_path):
    if not logo_path or not os.path.isfile(logo_path):
        return None, None
    ext  = os.path.splitext(logo_path)[1].lower()
    mime = {"png": "image/png", "svg": "image/svg+xml",
            "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext.lstrip("."), "image/png")
    with open(logo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return b64, mime


def parse_manifest(path):
    data   = {}
    genome = None
    entry  = None
    with open(path) as f:
        for line in f:
            raw      = line.rstrip("\n")
            stripped = raw.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(raw) - len(stripped)
            if indent == 0 and stripped.endswith(":"):
                genome = stripped[:-1]
                data[genome] = {}
                entry = None
            elif indent == 2 and stripped.endswith(":") and genome:
                entry = stripped[:-1]
                data[genome][entry] = {}
            elif indent == 4 and ":" in stripped and genome and entry:
                key, _, val = stripped.partition(":")
                val = val.strip().strip('"').strip("'")
                data[genome][entry][key.strip()] = val
    return data


def status(e):
    c = e.get("computed_sha256", "")
    x = e.get("expected_sha256", "")
    if not c:  return "pending"
    if c == x: return "ok"
    return "fail"

def status_label(s):
    return {"ok": "VERIFIED", "fail": "MISMATCH", "pending": "PENDING"}[s]


def build_report(yaml_path, output_path="setup_report.html",
                 logo_path=None, pipeline_version="—"):

    data    = parse_manifest(yaml_path)
    genome  = list(data.keys())[0]
    entries = data[genome]

    total      = len(entries)
    verified   = sum(1 for e in entries.values() if e.get("computed_sha256", ""))
    mismatches = sum(1 for e in entries.values()
                     if e.get("computed_sha256", "") and
                        e.get("computed_sha256", "") != e.get("expected_sha256", ""))
    pending    = total - verified
    ok_count   = verified - mismatches
    ok_pct     = ok_count   / total * 100 if total else 0
    fail_pct   = mismatches / total * 100 if total else 0

    # ── resource cards ────────────────────────────────────────────────────────
    rows = ""
    for key, e in entries.items():
        s   = status(e)
        lbl = status_label(s)
        comp = e.get("computed_sha256", "") or "—"
        exp  = e.get("expected_sha256",  "") or "—"

        if s == "fail":
            sha_block = f'''
            <div class="sha-block fail-sha">
              <div class="sha-row"><span class="sha-label">expected</span><code>{exp}</code></div>
              <div class="sha-row"><span class="sha-label">computed</span><code class="bad">{comp}</code></div>
            </div>'''
        elif s == "ok":
            sha_block = f'''
            <div class="sha-block ok-sha">
              <div class="sha-row"><span class="sha-label">sha256</span><code>{comp}</code></div>
            </div>'''
        else:
            sha_block = ""

        rows += f'''
        <div class="card {s}" data-status="{s}">
          <div class="card-header">
            <div class="card-left">
              <span class="badge {s}">{lbl}</span>
              <span class="card-key">{key}</span>
              <span class="card-db">{e.get("dbname", "")}</span>
            </div>
            <span class="card-version">v{e.get("version", "—")}</span>
          </div>
          <div class="card-body">
            <div class="card-meta">
              <span class="meta-item"><span class="meta-label">file</span>{e.get("out", "—")}</span>
              <span class="meta-item"><span class="meta-label">method</span>{e.get("method", "—")}</span>
            </div>
            {sha_block}
          </div>
        </div>'''

    # ── logo ──────────────────────────────────────────────────────────────────
    b64, mime = load_logo_base64(logo_path)
    logo_html = (f'<img src="data:{mime};base64,{b64}" class="logo-img" alt="MuSA"/>'
                 if b64 else '<span class="logo-fallback">MuSA</span>')

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>MuSA · Setup Report · {genome.upper()}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="{THEME['google_fonts']}" rel="stylesheet"/>
<style>
{css_vars(THEME)}

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-body);
    min-height: 100vh;
    overflow-x: hidden;
    font-size: 15px;
    line-height: 1.6;
  }}

  /* dot-grid texture */
  body::before {{
    content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-image: radial-gradient(circle, var(--border2) 1px, transparent 1px);
    background-size: 24px 24px; opacity: .18;
  }}

  /* ── header ─────────────────────────────────────────────────────────────── */
  header {{
    position: relative; z-index: 10;
    border-bottom: 1px solid var(--border);
    padding: 0 2.5rem;
    display: flex; align-items: center; justify-content: space-between;
    height: 56px;
    background: var(--surface);
    box-shadow: 0 1px 0 var(--border);
  }}
  .header-left {{
    display: flex; align-items: center; gap: .75rem;
  }}
  .header-logo {{
    height: 28px; width: auto; display: block; opacity: .9;
  }}
  .header-title {{
    font-size: .75rem; font-weight: 500; color: var(--muted);
    letter-spacing: .06em; text-transform: uppercase;
    border-left: 1px solid var(--border2); padding-left: .75rem;
  }}
  .header-right {{
    font-family: var(--font-mono); font-size: .68rem; color: var(--muted);
    display: flex; gap: 1.8rem; align-items: center;
  }}
  .header-right span {{ display: flex; gap: .35rem; align-items: center; }}
  .header-right b {{ color: var(--text); font-weight: 500; }}
  .version-badge {{
    font-family: var(--font-mono); font-size: .62rem;
    padding: .15rem .5rem; border-radius: 4px;
    background: var(--surface2); border: 1px solid var(--border2);
    color: var(--accent); letter-spacing: .05em;
  }}

  /* ── hero ───────────────────────────────────────────────────────────────── */
  .hero {{
    position: relative; z-index: 5;
    padding: 3rem 2.5rem 2.5rem;
    border-bottom: 1px solid var(--border); overflow: hidden;
    background: linear-gradient(135deg, #141828 0%, var(--bg) 60%);
  }}
  /* faint watermark */
  .hero::after {{
    content: "MuSA";
    position: absolute; right: -1rem; bottom: -1.5rem;
    font-family: var(--font-display); font-size: 11rem; font-weight: 700;
    line-height: 1; color: var(--accent); opacity: .04;
    pointer-events: none; letter-spacing: -.04em; user-select: none;
  }}

  /* logo + title on same row */
  .hero-top {{
    display: flex; align-items: center; gap: 2rem;
    margin-bottom: 1.6rem;
  }}
  .hero-logo {{
    /* size is driven by the two lines of h1 text (~line-height × 2) */
    height: 5rem;        /* adjust if your logo aspect ratio needs it */
    width: auto;
    flex-shrink: 0;
    filter: brightness(1.05);
  }}
  /* fallback text logo when no image */
  .logo-fallback {{
    font-family: var(--font-display); font-size: 2.4rem; font-weight: 700;
    color: var(--accent); letter-spacing: -.02em; flex-shrink: 0;
  }}
  .hero h1 {{
    font-family: var(--font-display);
    font-size: clamp(1.7rem, 3vw, 2.6rem);
    font-weight: 600; line-height: 1.2;
    letter-spacing: -.02em; color: var(--text);
  }}
  .hero h1 em {{
    font-style: italic; font-weight: 300;
    color: var(--accent);
  }}

  .hero-meta {{
    color: var(--muted); font-size: .75rem; margin-bottom: 2rem;
    font-family: var(--font-mono); letter-spacing: .03em;
    display: flex; gap: 1.5rem; flex-wrap: wrap;
  }}
  .hero-meta span {{ display: flex; gap: .4rem; align-items: center; }}
  .hero-meta b {{ color: var(--text); font-weight: 500; }}

  /* ── stat grid ───────────────────────────────────────────────────────────── */
  .stats {{
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 1px; background: var(--border);
    border: 1px solid var(--border); border-radius: var(--radius);
    overflow: hidden; margin-bottom: 2rem;
    box-shadow: 0 2px 12px rgba(0,0,0,.3);
  }}
  .stat {{
    background: var(--surface); padding: 1.1rem 1.4rem;
    display: flex; flex-direction: column; gap: .2rem;
  }}
  .stat-num {{
    font-family: var(--font-display); font-size: 2.4rem; font-weight: 700;
    line-height: 1; letter-spacing: -.03em;
  }}
  .stat-label {{
    font-family: var(--font-mono); font-size: .62rem;
    text-transform: uppercase; letter-spacing: .12em; color: var(--muted);
  }}
  .stat.ok    .stat-num {{ color: var(--ok); }}
  .stat.fail  .stat-num {{ color: var(--fail); }}
  .stat.pend  .stat-num {{ color: var(--pend); }}
  .stat.total .stat-num {{ color: var(--text); }}

  /* ── progress bar ────────────────────────────────────────────────────────── */
  .progress-wrap {{ margin-bottom: 0; }}
  .progress-label {{
    font-family: var(--font-mono); font-size: .68rem; color: var(--muted);
    margin-bottom: .4rem; display: flex; justify-content: space-between;
  }}
  .progress-label b {{ color: var(--text); font-weight: 500; }}
  .progress-track {{
    height: 6px; background: var(--surface2); border-radius: 99px;
    overflow: hidden; display: flex; border: 1px solid var(--border);
  }}
  .progress-ok   {{ height: 100%; background: var(--ok);   width: {ok_pct:.1f}%; transition: width 1s ease; }}
  .progress-fail {{ height: 100%; background: var(--fail); width: {fail_pct:.1f}%; transition: width 1s ease .1s; }}

  /* ── toolbar ─────────────────────────────────────────────────────────────── */
  .toolbar {{
    position: relative; z-index: 5; padding: .8rem 2.5rem;
    border-bottom: 1px solid var(--border);
    display: flex; gap: .4rem; align-items: center;
    background: var(--surface);
  }}
  .filter-btn {{
    font-family: var(--font-mono); font-size: .65rem;
    padding: .28rem .8rem; border-radius: 99px;
    border: 1px solid var(--border2);
    background: transparent; color: var(--muted); cursor: pointer;
    transition: all .15s; text-transform: uppercase; letter-spacing: .08em;
  }}
  .filter-btn:hover {{
    color: var(--text); border-color: var(--accent);
    background: var(--surface2);
  }}
  .filter-btn.active                   {{ color: var(--text);  border-color: var(--accent); background: #6c5fff18; }}
  .filter-btn[data-f="ok"].active      {{ border-color: var(--ok);   background: var(--ok-dim);   color: var(--ok); }}
  .filter-btn[data-f="fail"].active    {{ border-color: var(--fail); background: var(--fail-dim); color: var(--fail); }}
  .filter-btn[data-f="pending"].active {{ border-color: var(--pend); background: var(--pend-dim); color: var(--pend); }}

  .search {{
    margin-left: auto; font-family: var(--font-mono); font-size: .72rem;
    padding: .28rem 1rem; border-radius: 99px;
    border: 1px solid var(--border2);
    background: var(--surface2); color: var(--text); outline: none; width: 220px;
    transition: border-color .15s, box-shadow .15s;
  }}
  .search:focus {{ border-color: var(--accent); box-shadow: 0 0 0 3px #6c5fff20; }}
  .search::placeholder {{ color: var(--muted); }}

  /* ── resource cards ──────────────────────────────────────────────────────── */
  .grid {{
    position: relative; z-index: 5;
    padding: 1.5rem 2.5rem 4rem;
    display: flex; flex-direction: column; gap: .55rem;
  }}
  .card {{
    border: 1px solid var(--border); border-radius: var(--radius);
    background: var(--surface); overflow: hidden;
    transition: border-color .18s, transform .15s, box-shadow .18s;
    animation: slideIn .28s ease both;
  }}
  @keyframes slideIn {{ from {{ opacity:0; transform:translateY(6px); }} to {{ opacity:1; transform:translateY(0); }} }}
  .card:hover {{
    transform: translateX(3px);
    box-shadow: -3px 0 0 0 var(--accent), 0 4px 16px rgba(0,0,0,.35);
    border-color: var(--border2);
  }}
  .card.ok      {{ border-left: 3px solid var(--ok); }}
  .card.fail    {{
    border-left: 3px solid var(--fail);
    background: linear-gradient(90deg, var(--fail-dim) 0%, var(--surface) 40%);
  }}
  .card.pending {{ border-left: 3px solid var(--border); opacity: .6; }}

  .card-header {{
    padding: .65rem 1.2rem; display: flex; align-items: center;
    justify-content: space-between; border-bottom: 1px solid var(--border);
    gap: 1rem; background: var(--surface2);
  }}
  .card-left {{ display: flex; align-items: center; gap: .55rem; flex-wrap: wrap; }}

  .badge {{
    font-family: var(--font-mono); font-size: .56rem; font-weight: 500;
    padding: .15rem .48rem; border-radius: 4px;
    text-transform: uppercase; letter-spacing: .1em;
  }}
  .badge.ok      {{ background: var(--ok-dim);   color: var(--ok);   border: 1px solid var(--ok-border); }}
  .badge.fail    {{ background: var(--fail-dim);  color: var(--fail); border: 1px solid var(--fail-border); font-weight: 600; }}
  .badge.pending {{ background: var(--pend-dim);  color: var(--pend); border: 1px solid var(--pend-border); }}

  .card-key     {{ font-weight: 600; font-size: .9rem; color: var(--text); }}
  .card-db      {{ font-family: var(--font-mono); font-size: .65rem; color: var(--muted); }}
  .card-version {{ font-family: var(--font-mono); font-size: .62rem; color: var(--muted); white-space: nowrap; }}

  .card-body  {{ padding: .7rem 1.2rem; display: flex; flex-direction: column; gap: .5rem; }}
  .card-meta  {{ display: flex; gap: 1.8rem; flex-wrap: wrap; }}
  .meta-item  {{
    font-family: var(--font-mono); font-size: .65rem; color: var(--muted);
    display: flex; gap: .35rem; align-items: center;
  }}
  .meta-label {{
    color: var(--border2); font-size: .58rem;
    text-transform: uppercase; letter-spacing: .1em;
  }}
  /* make meta values clearly readable */
  .meta-item span:last-child {{ color: var(--text); }}

  .sha-block  {{ border-radius: 6px; padding: .5rem .85rem; display: flex; flex-direction: column; gap: .3rem; }}
  .sha-block.ok-sha   {{ background: var(--ok-dim);   border: 1px solid var(--ok-border); }}
  .sha-block.fail-sha {{ background: var(--fail-dim); border: 1px solid var(--fail-border); }}
  .sha-row    {{ display: flex; gap: .6rem; align-items: baseline; flex-wrap: wrap; }}
  .sha-label  {{
    font-family: var(--font-mono); font-size: .56rem; color: var(--muted);
    text-transform: uppercase; letter-spacing: .1em; min-width: 5rem; flex-shrink: 0;
  }}
  code        {{ font-family: var(--font-mono); font-size: .63rem; color: var(--text); word-break: break-all; line-height: 1.5; }}
  code.bad    {{ color: var(--fail); font-weight: 600; }}

  .empty {{
    text-align: center; padding: 4rem 1rem; color: var(--muted);
    font-family: var(--font-mono); font-size: .8rem; display: none;
  }}

  /* ── footer ──────────────────────────────────────────────────────────────── */
  footer {{
    position: relative; z-index: 5; border-top: 1px solid var(--border);
    padding: .9rem 2.5rem; display: flex; justify-content: space-between;
    align-items: center; font-family: var(--font-mono); font-size: .62rem;
    color: var(--muted); background: var(--surface);
  }}

  @media (max-width: 680px) {{
    .stats {{ grid-template-columns: repeat(2,1fr); }}
    .hero-top {{ flex-direction: column; align-items: flex-start; gap: 1rem; }}
    .hero-logo {{ height: 3rem; }}
    header, .hero, .toolbar, .grid, footer {{ padding-left: 1rem; padding-right: 1rem; }}
    .hero::after {{ font-size: 6rem; }}
    .header-right {{ gap: 1rem; }}
  }}
</style>
</head>
<body>

<!-- ── header ── -->
<header>
  <div class="header-left">
    {f'<img src="data:{mime};base64,{b64}" class="header-logo" alt="MuSA"/>' if b64 else ''}
    <span class="header-title">Setup Report</span>
  </div>
  <div class="header-right">
    <span>genome <b>{genome.upper()}</b></span>
    <span><span class="version-badge">{pipeline_version}</span></span>
    <span>generated <b>{now}</b></span>
  </div>
</header>

<!-- ── hero ── -->
<div class="hero">
  <div class="hero-top">
    {f'<img src="data:{mime};base64,{b64}" class="hero-logo" alt="MuSA"/>' if b64 else f'<span class="logo-fallback">MuSA</span>'}
    <h1>MuSA resource<br/><em>Integrity report</em></h1>
  </div>
  <div class="hero-meta">
    <span>genome build <b>{genome.upper()}</b></span>
    <span>pipeline <b>{pipeline_version}</b></span>
    <span>{total} resources tracked</span>
  </div>
  <div class="stats">
    <div class="stat total"><span class="stat-num">{total}</span>      <span class="stat-label">Total Resources</span></div>
    <div class="stat ok">   <span class="stat-num">{ok_count}</span>   <span class="stat-label">Verified OK</span></div>
    <div class="stat fail"> <span class="stat-num">{mismatches}</span> <span class="stat-label">SHA Mismatch</span></div>
    <div class="stat pend"> <span class="stat-num">{pending}</span>    <span class="stat-label">Pending</span></div>
  </div>
  <div class="progress-wrap">
    <div class="progress-label">
      <span>integrity coverage</span>
      <span><b>{verified}</b> / {total} verified</span>
    </div>
    <div class="progress-track">
      <div class="progress-ok"></div>
      <div class="progress-fail"></div>
    </div>
  </div>
</div>

<!-- ── toolbar ── -->
<div class="toolbar">
  <button class="filter-btn active" data-f="all">All <span style="opacity:.5">({total})</span></button>
  <button class="filter-btn" data-f="ok">Verified <span style="opacity:.5">({ok_count})</span></button>
  <button class="filter-btn" data-f="fail">Mismatch <span style="opacity:.5">({mismatches})</span></button>
  <button class="filter-btn" data-f="pending">Pending <span style="opacity:.5">({pending})</span></button>
  <input class="search" type="text" placeholder="search resources…" id="search"/>
</div>

<!-- ── cards ── -->
<div class="grid" id="grid">
{rows}
  <div class="empty" id="empty">No resources match your filter.</div>
</div>

<!-- ── footer ── -->
<footer>
  <span>MuSA · Multi Source Variant Annotation</span>
  <span>Made with ❤ at IRCCS Istituto Ortopedico Rizzoli, Bologna, Italy</span>
  <span>{now}</span>
</footer>

<script>
  const cards = [...document.querySelectorAll('.card')];
  const empty  = document.getElementById('empty');
  const search = document.getElementById('search');
  let activeFilter = 'all';
  cards.forEach((c, i) => c.style.animationDelay = i * 14 + 'ms');

  function applyFilters() {{
    const q = search.value.toLowerCase();
    let visible = 0;
    cards.forEach(c => {{
      const matchF = activeFilter === 'all' || c.dataset.status === activeFilter;
      const matchQ = !q || c.textContent.toLowerCase().includes(q);
      const show   = matchF && matchQ;
      c.style.display = show ? '' : 'none';
      if (show) visible++;
    }});
    empty.style.display = visible === 0 ? 'block' : 'none';
  }}

  document.querySelectorAll('.filter-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeFilter = btn.dataset.f;
      applyFilters();
    }});
  }});

  search.addEventListener('input', applyFilters);
</script>

</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)

    print(f"Report written to {output_path}: {total} resources, "
          f"{ok_count} verified, {mismatches} mismatches, {pending} pending")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: build_setup_report.py <manifest.yaml> [output.html] [logo.png] [pipeline_version]")
        sys.exit(1)
    yaml_path         = sys.argv[1]
    output_path       = sys.argv[2] if len(sys.argv) > 2 else "setup_report.html"
    logo_path         = sys.argv[3] if len(sys.argv) > 3 else None
    pipeline_version  = sys.argv[4] if len(sys.argv) > 4 else "v?.?.?"
    build_report(yaml_path, output_path, logo_path, pipeline_version)