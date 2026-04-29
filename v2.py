#!/usr/bin/env python3
"""
VENV REAPER — Streamlit Matrix UI  v3.0
Run: streamlit run venv_reaper_ui.py
Requires: pip install streamlit pandas
"""

import time
from pathlib import Path

import streamlit as st

from venv_reaper.core import fmt_size, scan_directory, size_color
from venv_reaper.core.discovery import get_drives, list_subdirs
from venv_reaper.core.quarantine import inter as crypt_inter
from venv_reaper.theme import matrix_rain_block, style_block

# ──────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be first Streamlit call)
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VENV REAPER",
    page_icon="☠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────────────────────
# MATRIX RAIN — injected into parent document
# ──────────────────────────────────────────────────────────────────────────────
st.html(matrix_rain_block())

# ──────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS
# ──────────────────────────────────────────────────────────────────────────────
st.markdown(style_block(), unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ──────────────────────────────────────────────────────────────────────────────
_DEFAULTS = {
    "scan_results":    [],
    "log":             [],
    "scan_done":       False,
    "confirm_delete":  False,
    "deleted_count":   0,
    "freed_bytes":     0,
    "browser_open":    False,
    "browser_cwd":     str(Path.home()),
    "selected_path":   str(Path.home()),
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ──────────────────────────────────────────────────────────────────────────────
# LOG HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def log(msg: str, kind: str = "ok"):
    ts = time.strftime("%H:%M:%S")
    st.session_state.log.append((ts, msg, kind))


def render_log():
    if not st.session_state.log:
        return
    lines = [
        f'<span class="t-dim">[{ts}]</span> <span class="t-{k}">{m}</span>'
        for ts, m, k in reversed(st.session_state.log[-60:])
    ]
    st.markdown(f'<div class="terminal">{"<br>".join(lines)}</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# STAT BOXES
# ──────────────────────────────────────────────────────────────────────────────
def render_stats(results: list[dict]):
    total_b = sum(r["_size_bytes"] for r in results)
    val, unit = fmt_size(total_b)
    has_req = sum(1 for r in results if r["_req_path"])
    sc = size_color(total_b)
    st.markdown(f"""
    <div class="stat-row">
      <div class="stat-box">
        <div class="stat-num">{len(results)}</div>
        <div class="stat-label">Venvs Found</div>
      </div>
      <div class="stat-box">
        <div class="stat-num" style="color:{sc}">{val}<span class="stat-unit"> {unit}</span></div>
        <div class="stat-label">Disk Consumed</div>
      </div>
      <div class="stat-box">
        <div class="stat-num" style="color:#00e5ff">{has_req}</div>
        <div class="stat-label">With Req.txt</div>
      </div>
      <div class="stat-box">
        <div class="stat-num" style="color:#ff2222">{len(results) - has_req}</div>
        <div class="stat-label">No Req.txt</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# BREADCRUMB
# ──────────────────────────────────────────────────────────────────────────────
def render_breadcrumb(path: Path):
    parts = path.parts
    html  = '<div class="breadcrumb-bar">'
    for i, part in enumerate(parts):
        cls = "bc-last" if i == len(parts) - 1 else "bc-part"
        html += f'<span class="{cls}">{part}</span>'
        if i < len(parts) - 1:
            html += '<span class="bc-sep"> / </span>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# DIRECTORY BROWSER
# ──────────────────────────────────────────────────────────────────────────────
def render_dir_browser():
    cwd     = Path(st.session_state.browser_cwd)
    subdirs = list_subdirs(cwd)
    drives  = get_drives()

    st.markdown('<div class="dir-browser fade-in">', unsafe_allow_html=True)

    # Title bar
    st.markdown("""
    <div class="dir-titlebar">
      <span style="color:#00e5ff; font-size:1.05rem;">📂</span>
      <span class="dir-titlebar-label">DIRECTORY NAVIGATOR</span>
      <span style="margin-left:auto; color:#1a4a4a; font-size:0.62rem; letter-spacing:1px;">
        CLICK FOLDER TO ENTER &nbsp;·&nbsp; HIT SELECT TO CONFIRM
      </span>
    </div>""", unsafe_allow_html=True)

    # Breadcrumb
    render_breadcrumb(cwd)

    st.markdown("<div style='padding:0.5rem 0.6rem;'>", unsafe_allow_html=True)

    # ── Nav controls ──────────────────────────────────────────────────────────
    nav_c1, nav_c2, nav_c3, nav_c4 = st.columns([1, 1, 1, 5])
    with nav_c1:
        st.markdown('<div class="btn-cyan">', unsafe_allow_html=True)
        if st.button("⬆ PARENT", use_container_width=True, key="nav_up"):
            parent = cwd.parent
            if parent != cwd:
                st.session_state.browser_cwd = str(parent)
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with nav_c2:
        if st.button("🏠 HOME", use_container_width=True, key="nav_home"):
            st.session_state.browser_cwd = str(Path.home())
            st.rerun()
    with nav_c3:
        if st.button("⟳ REFRESH", use_container_width=True, key="nav_refresh"):
            st.rerun()

    # Drive buttons (Windows multi-drive / Unix shortcut)
    if len(drives) > 1:
        st.markdown("<div style='margin-top:4px;'>", unsafe_allow_html=True)
        d_cols = st.columns(min(len(drives), 10))
        for i, d in enumerate(drives):
            with d_cols[i]:
                if st.button(f"💾 {d}", key=f"drive_{d}", use_container_width=True):
                    st.session_state.browser_cwd = d
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Folder grid ───────────────────────────────────────────────────────────
    st.markdown("<div style='margin-top:0.5rem;'>", unsafe_allow_html=True)

    if not subdirs:
        st.markdown("""
        <div style="padding:1.2rem; text-align:center; color:#1a4020; font-size:0.8rem;
                    border:1px dashed #0a2010; border-radius:3px;">
          ∅ &nbsp; No subdirectories &nbsp; ∅
        </div>""", unsafe_allow_html=True)
    else:
        COLS = 4
        for row_start in range(0, len(subdirs), COLS):
            row  = subdirs[row_start: row_start + COLS]
            cols = st.columns(COLS)
            for j, folder in enumerate(row):
                with cols[j]:
                    # Truncate long names for display
                    label = folder.name if len(folder.name) <= 22 else folder.name[:19] + "..."
                    if st.button(f"📁 {label}", key=f"folder_{folder}", use_container_width=True):
                        st.session_state.browser_cwd = str(folder)
                        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ── Current dir display + action buttons ──────────────────────────────────
    st.markdown(f"""
    <div class="selected-path-display">
      <span class="sp-label">NAVIGATED TO</span>
      {str(cwd)}
    </div>""", unsafe_allow_html=True)

    sel_col, close_col, _ = st.columns([2.2, 1, 4])
    with sel_col:
        st.markdown('<div class="btn-primary">', unsafe_allow_html=True)
        if st.button("✔  SELECT THIS DIRECTORY", use_container_width=True, key="browser_select"):
            st.session_state.selected_path  = str(cwd)
            st.session_state.browser_open   = False
            st.session_state.scan_results   = []
            st.session_state.scan_done      = False
            st.session_state.confirm_delete = False
            log(f"Target directory locked: {cwd}", "info")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with close_col:
        if st.button("✘ CLOSE", use_container_width=True, key="browser_close"):
            st.session_state.browser_open = False
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)  # end padding div
    st.markdown('</div>', unsafe_allow_html=True)   # end dir-browser


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="text-align:center; padding:1.5rem 0 0.6rem;">
  <div style="font-family:'Orbitron',monospace; font-size:2.4rem; font-weight:900;
              color:#00ff41; letter-spacing:8px;
              text-shadow:0 0 20px #00ff41, 0 0 60px #00bb30, 0 0 100px #004d10;">
    ☠ &nbsp; V E N V &nbsp; R E A P E R &nbsp; ☠
  </div>
  <div style="color:#3a6a40; font-size:0.7rem; letter-spacing:5px; margin-top:6px;">
    HUNT &nbsp;·&nbsp; INSPECT &nbsp;·&nbsp; DESTROY &nbsp;·&nbsp; REPEAT
  </div>
  <div style="margin-top:10px; display:inline-block;
              border:1px solid #004d10; border-radius:3px;
              padding:4px 18px;
              background:rgba(0,30,0,0.5);
              box-shadow:0 0 12px rgba(0,255,65,0.12);">
    <span style="color:#4a7a50; font-size:0.65rem; letter-spacing:2px;">A SOLUTION BY &nbsp;</span><span style="color:#00ff41; font-family:'Orbitron',monospace; font-size:0.7rem; letter-spacing:3px; text-shadow:0 0 8px #00ff41;">DEEP MALVIYA</span>
  </div>
</div>
<hr>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TARGET ACQUISITION PANEL
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="section-label">// TARGET ACQUISITION</div>', unsafe_allow_html=True)

# Active path pill
selected_path = st.session_state.selected_path
st.markdown(f"""
<div class="selected-path-display">
  <span class="sp-label">LOCKED TARGET DIRECTORY</span>
  {selected_path}
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns([1.8, 1.5, 1, 1])

with c1:
    st.markdown('<div class="btn-cyan">', unsafe_allow_html=True)
    browse_label = "📂 CLOSE BROWSER" if st.session_state.browser_open else "📂 BROWSE DIRECTORY"
    if st.button(browse_label, use_container_width=True, key="toggle_browser"):
        st.session_state.browser_open = not st.session_state.browser_open
        if st.session_state.browser_open:
            st.session_state.browser_cwd = st.session_state.selected_path
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with c2:
    st.markdown('<div class="btn-primary">', unsafe_allow_html=True)
    do_scan = st.button("⚡ INITIATE SCAN", use_container_width=True, key="scan_btn")
    st.markdown('</div>', unsafe_allow_html=True)

with c3:
    if st.button("CLR RESULTS", use_container_width=True, key="clear_btn"):
        st.session_state.scan_results   = []
        st.session_state.log            = []
        st.session_state.scan_done      = False
        st.session_state.confirm_delete = False
        st.rerun()

with c4:
    if st.button("🏠 RESET ALL", use_container_width=True, key="reset_btn"):
        for k, v in _DEFAULTS.items():
            st.session_state[k] = v
        st.rerun()

st.markdown('</div>', unsafe_allow_html=True)  # end card

# ── Directory browser (conditional) ──────────────────────────────────────────
if st.session_state.browser_open:
    render_dir_browser()

# ──────────────────────────────────────────────────────────────────────────────
# HANDLE SCAN
# ──────────────────────────────────────────────────────────────────────────────
if do_scan:
    root = Path(st.session_state.selected_path).resolve()
    st.session_state.scan_done      = False
    st.session_state.confirm_delete = False
    st.session_state.browser_open   = False

    if not root.exists() or not root.is_dir():
        log(f"INVALID PATH: {root}", "err")
        st.session_state.scan_results = []
        st.rerun()
    else:
        log(f"Scan initiated on: {root}", "info")
        _loader = st.empty()
        _loader.markdown("""
<div class="hacker-loader">
  <div class="hl-title">// INITIATING SCAN SEQUENCE <span class="hl-cursor">▋</span></div>
  <div class="hl-bar-wrap"><div class="hl-bar"></div></div>
  <div class="hl-line hl-l1"><span>[SYS]</span> Mounting filesystem walker...</div>
  <div class="hl-line hl-l2"><span>[VEN]</span> Loading venv signature database...</div>
  <div class="hl-line hl-l3"><span>[SCN]</span> Traversing directory tree recursively...</div>
  <div class="hl-line hl-l4"><span>[CHK]</span> Checking pyvenv.cfg · bin/python · Scripts/python.exe</div>
  <div class="hl-line hl-l5"><span>[REQ]</span> Hunting requirements.txt in parent scopes...</div>
  <div class="hl-line hl-l6 dim">// stand by — calculating disk usage...</div>
</div>
""", unsafe_allow_html=True)
        results = scan_directory(root)
        _loader.empty()
        st.session_state.scan_results = results
        st.session_state.scan_done    = True
        if results:
            tb = sum(r["_size_bytes"] for r in results)
            v, u = fmt_size(tb)
            log(f"Scan complete — {len(results)} venv(s) detected  ·  {v} {u} total", "ok")
        else:
            log("Scan complete — no virtual environments found in target", "warn")
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# RESULTS
# ══════════════════════════════════════════════════════════════════════════════
results = st.session_state.scan_results

if results:
    st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)

    # Stats
    st.markdown('<div class="section-label">// RECON SUMMARY</div>', unsafe_allow_html=True)
    render_stats(results)
    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Hacker Table ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">// SELECT TARGETS — TICK BOXES, THEN STRIKE</div>', unsafe_allow_html=True)

    # Table header
    st.markdown("""
<div class="ht-wrap">
  <div class="ht-head">
    <div class="ht-hcell">☑</div>
    <div class="ht-hcell">ENV NAME</div>
    <div class="ht-hcell">PATH</div>
    <div class="ht-hcell">SIZE</div>
    <div class="ht-hcell">DEPTH</div>
    <div class="ht-hcell">REQUIREMENTS</div>
  </div>
</div>""", unsafe_allow_html=True)

    selected_indices = []
    for i, r in enumerate(results):
        mb   = r["_size_bytes"] / (1024**2)
        sc   = "sz-ok" if mb < 50 else ("sz-med" if mb < 200 else ("sz-high" if mb < 500 else "sz-crit"))
        req_cls  = "req-yes" if r["_req_path"] else "req-no"
        req_icon = "✔  FOUND" if r["_req_path"] else "✘  MISSING"
        is_sel   = r["Select"]
        row_cls  = "ht-row selected" if is_sel else "ht-row"
        depth    = r["DEPTH"]
        depth_bar = "█" * min(depth + 1, 5)

        cb_col, row_col = st.columns([0.28, 11])
        with cb_col:
            st.markdown('<div class="ht-cb-col">', unsafe_allow_html=True)
            checked = st.checkbox("x", key=f"cb_{i}", value=is_sel, label_visibility="hidden")
            st.markdown('</div>', unsafe_allow_html=True)
            if checked != r["Select"]:
                st.session_state.scan_results[i]["Select"] = checked
                st.rerun()
            if checked:
                selected_indices.append(i)

        with row_col:
            st.markdown(f"""
<div class="{row_cls}" style="margin-left:-0.5rem;">
  <div class="ht-cell" style="display:none"></div>
  <div class="ht-cell name" title="{r['ENV NAME']}">{r['ENV NAME']}</div>
  <div class="ht-cell path" title="{r['RELATIVE PATH']}">{r['RELATIVE PATH']}</div>
  <div class="ht-cell {sc}">{r['SIZE']}</div>
  <div class="ht-cell depth" title="Depth {depth}">{depth_bar} L{depth}</div>
  <div class="ht-cell {req_cls}">{req_icon}</div>
</div>""", unsafe_allow_html=True)

    n_sel = len(selected_indices)

    # Quick-select
    st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)
    qa, qb, qc, _ = st.columns([1, 1, 1, 6])
    with qa:
        if st.button("SELECT ALL", use_container_width=True, key="sel_all"):
            for r in st.session_state.scan_results: r["Select"] = True
            st.rerun()
    with qb:
        if st.button("CLEAR ALL", use_container_width=True, key="sel_none"):
            for r in st.session_state.scan_results: r["Select"] = False
            st.rerun()
    with qc:
        if st.button("INVERT", use_container_width=True, key="sel_invert"):
            for r in st.session_state.scan_results: r["Select"] = not r["Select"]
            st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Strike Package ────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">// STRIKE PACKAGE</div>', unsafe_allow_html=True)

    if n_sel == 0:
        st.markdown("""
        <div style="color:#2a5030; font-size:0.82rem; padding:0.5rem 0; letter-spacing:1px;">
          ⚠  No targets selected. Use checkboxes or quick-select buttons above.
        </div>""", unsafe_allow_html=True)
    else:
        sel_bytes    = sum(results[i]["_size_bytes"] for i in selected_indices)
        sv, su       = fmt_size(sel_bytes)
        sel_with_req = sum(1 for i in selected_indices if results[i]["_req_path"])
        no_req_count = n_sel - sel_with_req
        sc           = size_color(sel_bytes)

        st.markdown(f"""
        <div class="card" style="border-color:#3a0000;box-shadow:0 0 18px rgba(255,34,34,0.12);">
          <div style="font-family:'Orbitron',monospace;font-size:0.68rem;color:#cc2222;letter-spacing:2px;margin-bottom:0.7rem;">
            ⚠ TARGETS LOCKED — AWAITING AUTHORIZATION
          </div>
          <div class="stat-row">
            <div class="stat-box" style="border-color:#3a0000;">
              <div class="stat-num" style="color:#ff2222">{n_sel}</div>
              <div class="stat-label">Targeted</div>
            </div>
            <div class="stat-box" style="border-color:#3a0000;">
              <div class="stat-num" style="color:{sc}">{sv}<span class="stat-unit"> {su}</span></div>
              <div class="stat-label">Will Be Freed</div>
            </div>
            <div class="stat-box" style="border-color:#3a0000;">
              <div class="stat-num" style="color:#00ff41">{sel_with_req}</div>
              <div class="stat-label">Have Req.txt</div>
            </div>
            <div class="stat-box" style="border-color:#3a0000;">
              <div class="stat-num" style="color:#ff8c00">{no_req_count}</div>
              <div class="stat-label">No Req.txt ⚠</div>
            </div>
          </div>
          {"'<div style=font-size:0.76rem;color:#884444;margin-top:0.3rem;>⚠ " + str(no_req_count) + " venv(s) have no requirements.txt — recreation may not be possible.</div>'" if no_req_count else ""}
        </div>
        """, unsafe_allow_html=True)

        # Preview targets
        with st.expander("👁  PREVIEW SELECTED TARGETS", expanded=False):
            for i in selected_indices:
                r = results[i]
                v2, u2   = fmt_size(r["_size_bytes"])
                req_icon = "✔" if r["_req_path"] else "✘"
                req_c    = "#00ff41" if r["_req_path"] else "#ff5555"
                sc2      = size_color(r["_size_bytes"])
                st.markdown(f"""
                <div style="font-size:0.8rem; border-left:2px solid #ff2222;
                            padding:0.3rem 0.8rem; margin-bottom:3px;
                            background:rgba(35,0,0,0.4); border-radius:0 3px 3px 0;">
                  <span style="color:#ff5555">►</span>
                  <span style="color:#ffbbbb; margin:0 0.5rem;">{r['ENV NAME']}</span>
                  <span style="color:#444">·</span>
                  <span style="color:#555; margin-left:0.5rem; font-size:0.75rem;">{r['RELATIVE PATH']}</span>
                  <span style="color:{sc2}; float:right; margin-left:1rem;">{v2} {u2}</span>
                  <span style="color:{req_c}; float:right;">{req_icon} REQ</span>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        # Confirm flow
        if not st.session_state.confirm_delete:
            d_col, _ = st.columns([2.2, 6])
            with d_col:
                st.markdown('<div class="btn-danger">', unsafe_allow_html=True)
                if st.button(f"⚡ DELETE {n_sel} VENV(S)", use_container_width=True, key="delete_btn"):
                    st.session_state.confirm_delete = True
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="font-family:'Orbitron',monospace;color:#ff2222;
                        font-size:0.8rem;letter-spacing:2px;padding:0.4rem 0;
                        text-shadow:0 0 10px #ff2222;">
              ⚠ &nbsp; CONFIRM DESTRUCTION — THIS CANNOT BE UNDONE
            </div>""", unsafe_allow_html=True)

            yes_col, no_col, _ = st.columns([1.2, 1, 6])
            with yes_col:
                st.markdown('<div class="btn-danger">', unsafe_allow_html=True)
                if st.button("✔ EXECUTE", use_container_width=True, key="exec_btn"):
                    freed = 0; killed = 0
                    log(f"Executing deletion of {n_sel} target(s)...", "warn")
                    prog = st.progress(0, text="Initialising strike...")
                    for step, i in enumerate(selected_indices):
                        r    = results[i]
                        path = Path(r["_path"])
                        try:
                            crypt_inter(path, size_bytes=r["_size_bytes"])
                            freed += r["_size_bytes"]; killed += 1
                            v3, u3 = fmt_size(r["_size_bytes"])
                            log(f"INTERRED ⚰  {path.name}  ({v3} {u3} sent to Crypt)", "ok")
                        except Exception as e:
                            log(f"FAILED ✘  {path.name} — {e}", "err")
                        prog.progress(
                            (step + 1) / len(selected_indices),
                            text=f"Eliminating {step + 1}/{len(selected_indices)}..."
                        )
                        time.sleep(0.04)
                    prog.empty()
                    fv, fu = fmt_size(freed)
                    log(f"Operation complete — {killed} eliminated · {fv} {fu} reclaimed", "ok")
                    deleted_paths = {results[i]["_path"] for i in selected_indices}
                    st.session_state.scan_results = [
                        r for r in st.session_state.scan_results
                        if r["_path"] not in deleted_paths
                    ]
                    st.session_state.confirm_delete  = False
                    st.session_state.deleted_count  += killed
                    st.session_state.freed_bytes    += freed
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            with no_col:
                if st.button("✘ ABORT", use_container_width=True, key="abort_btn"):
                    st.session_state.confirm_delete = False
                    log("Deletion aborted by operator.", "warn")
                    st.rerun()

elif st.session_state.scan_done:
    st.markdown("""
    <div class="card" style="text-align:center;padding:2rem;margin-top:1rem;">
      <div style="font-size:2.2rem;color:#00ff41;margin-bottom:0.5rem;">✔</div>
      <div style="font-family:'Orbitron',monospace;color:#00ff41;letter-spacing:3px;font-size:1rem;">
        DIRECTORY IS CLEAN
      </div>
      <div style="color:#3a6a40;font-size:0.78rem;margin-top:0.5rem;">
        No virtual environments detected in the target directory.
      </div>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SESSION TOTALS
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.deleted_count > 0:
    st.markdown("<hr>", unsafe_allow_html=True)
    fv, fu = fmt_size(st.session_state.freed_bytes)
    st.markdown(f"""
    <div class="section-label">// SESSION TOTALS</div>
    <div class="stat-row">
      <div class="stat-box">
        <div class="stat-num" style="color:#ff2222">{st.session_state.deleted_count}</div>
        <div class="stat-label">Venvs Destroyed</div>
      </div>
      <div class="stat-box">
        <div class="stat-num" style="color:#00ff41">{fv}<span class="stat-unit"> {fu}</span></div>
        <div class="stat-label">Space Reclaimed</div>
      </div>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TERMINAL LOG
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.log:
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div class="section-label">// SYSTEM LOG</div>', unsafe_allow_html=True)
    render_log()

# ══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="text-align:center;margin-top:2.5rem;padding-bottom:1.5rem;">
  <div style="margin-bottom:6px;">
    <span style="color:#4a7a50;font-size:0.6rem;letter-spacing:2px;">CRAFTED WITH ⚡ BY &nbsp;</span>
    <span style="font-family:'Orbitron',monospace;color:#00ff41;font-size:0.65rem;letter-spacing:3px;
                 text-shadow:0 0 8px #00ff41;">DEEP MALVIYA</span>
  </div>
  <div style="color:#0d200d;font-size:0.55rem;letter-spacing:3px;">
    VENV REAPER &nbsp;·&nbsp; KONVERGE.AI DEV OPS &nbsp;·&nbsp; <span class="cursor">█</span>
  </div>
</div>
""", unsafe_allow_html=True)