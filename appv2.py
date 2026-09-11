# ============================================================
# BCMV / BCMNV RESISTANCE MARKER DATABASE
# Accessible & Space-Optimized Streamlit UI
# ============================================================

import os
import re
import sqlite3
import pandas as pd
import streamlit as st

DB_NAME = "bcmv_markers.db"

st.set_page_config(
    page_title="Bean Resistance Genomics",
    page_icon="🫘",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Colorblind-Safe Color Palette (Okabe-Ito Inspired) ----------
COLOR_FWD_A = "#0072B2"  # Blue
COLOR_FWD_B = "#D55E00"  # Vermilion / Orange-Red
COLOR_REV   = "#009E73"  # Bluish Green
COLOR_ACCENT= "#CC79A7"  # Reddish Purple

# ---------- Accessible & Compact CSS ----------
st.markdown(f"""
<style>
    /* Compact main padding to reduce overall page height */
    .block-container {{
        max-width: 1450px;
        padding-top: 1.2rem;
        padding-bottom: 1.5rem;
    }}

    /* Hide unnecessary UI overhead */
    #MainMenu, footer {{ visibility: hidden; }}

    /* Compact sidebar styling */
    section[data-testid="stSidebar"] {{
        border-right: 1px solid rgba(128,128,128,.2);
    }}

    /* Metrics styling with accessible border */
    div[data-testid="stMetric"] {{
        background: rgba(128,128,128,.06);
        border: 1px solid rgba(128,128,128,.25);
        padding: .5rem .8rem;
        border-radius: 8px;
    }}

    /* Muted text readability */
    .muted {{ opacity: .75; font-weight: 500; }}

    /* Standardized height limits on dataframes to avoid page-length scrolling */
    div[data-testid="stDataFrame"] {{
        border-radius: 8px;
        border: 1px solid rgba(128,128,128,.2);
    }}

    /* Compact UI vertical spacing */
    div[data-testid="stVerticalBlock"] > div {{
        gap: .45rem;
    }}

    /* Custom highlight mark for sequence viewer */
    mark.seq-highlight {{
        background-color: #FFEA80;
        color: #000000;
        padding: 2px 4px;
        border-radius: 3px;
        border-bottom: 2px solid {COLOR_FWD_A};
        font-weight: bold;
    }}
</style>
""", unsafe_allow_html=True)


# ---------- Database helpers ----------
@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def run_query(query, params=()):
    return pd.read_sql_query(query, get_connection(), params=tuple(params))


def safe_count(table_name):
    try:
        return int(run_query(
            f"SELECT COUNT(*) AS count FROM {table_name}"
        )["count"].iloc[0])
    except Exception:
        return None


def section(title, subtitle=None, icon=None):
    label = f"{icon} {title}" if icon else title
    st.markdown(f"### {label}")
    if subtitle:
        st.caption(subtitle)


def metric_row(counts):
    cols = st.columns(len(counts))
    for col, (label, value) in zip(cols, counts.items()):
        with col:
            st.metric(label, value if value is not None else "—")


# ---------- Database check ----------
if not os.path.exists(DB_NAME):
    st.error(
        f"Database `{DB_NAME}` was not found. "
        "Place it beside this script and reload the app."
    )
    st.stop()


# ============================================================
# SIDEBAR / NAVIGATION
# ============================================================
with st.sidebar:
    st.markdown("## 🫘 Bean Genomics")
    st.caption("BCMV / BCMNV resistance markers")

    page = st.radio(
        "MODULE",
        [
            "Overview",
            "Loci Browser",
            "Marker Search",
            "Primer Map",
            "FASTA Viewer",
            "SQL Console",
        ],
        label_visibility="visible",
    )

    st.divider()
    st.caption("Phaseolus vulgaris L.")
    st.caption("Database: `bcmv_markers.db`")


# ============================================================
# 1. OVERVIEW
# ============================================================
if page == "Overview":
    st.title("Bean Resistance Genomics")
    st.caption("A compact browser for resistance loci, diagnostic markers, primers, and reference sequences.")

    counts = {
        "Genes": safe_count("genes"),
        "Markers": safe_count("markers"),
        "Primer sets": safe_count("primers"),
        "Sequences": safe_count("sequences"),
    }
    metric_row(counts)

    if any(v is None for v in counts.values()):
        st.warning("One or more expected database tables are missing.")

    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("📁 Browse Raw Database Tables", expanded=True):
        tabs = st.tabs(["Genes", "Markers", "Primers", "Sequences"])
        for tab, table in zip(tabs, ["genes", "markers", "primers", "sequences"]):
            with tab:
                df = run_query(f"SELECT * FROM {table}")
                st.dataframe(df, use_container_width=True, hide_index=True, height=300)


# ============================================================
# 2. LOCI BROWSER
# ============================================================
elif page == "Loci Browser":
    st.title("Loci Browser")

    genes_df = run_query("SELECT * FROM genes")

    if genes_df.empty:
        st.info("No genes found in the database.")
    else:
        gene_names = genes_df["gene_name"].dropna().tolist()
        
        c_sel, _ = st.columns([1, 2])
        with c_sel:
            selected_gene = st.selectbox("Target locus", gene_names)

        gene_info = genes_df.loc[genes_df["gene_name"] == selected_gene].iloc[0]

        st.markdown(
            f"### `{gene_info['gene_symbol']}` <span class='muted'>({gene_info['gene_name']})</span>",
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns([1, 1.5, 2])
        c1.metric("Chromosome / LG", gene_info["chromosome"])
        c2.metric("Candidate Annotation", gene_info["candidate_gene_annotation"])
        with c3:
            st.markdown("**Description**")
            st.caption(gene_info["description"])

        markers_query = """
            SELECT
                m.marker_name,
                m.target_allele,
                m.marker_type,
                m.Chromosome,
                m.reference,
                p.forward_primer_A,
                p.forward_primer_B,
                p.common_reverse_primer,
                p.expected_allele_size_or_call
            FROM markers m
            LEFT JOIN primers p ON m.marker_name = p.marker_name
            WHERE m.target_gene = ?
        """
        associated = run_query(markers_query, (selected_gene,))

        section(f"Associated Markers ({len(associated)})", "Diagnostic assays linked to this locus.")
        st.dataframe(associated, use_container_width=True, hide_index=True, height=280)


# ============================================================
# 3. MARKER SEARCH
# ============================================================
elif page == "Marker Search":
    st.title("Marker Search")

    all_genes = ["All"] + run_query(
        "SELECT DISTINCT gene_name FROM genes ORDER BY gene_name"
    )["gene_name"].dropna().tolist()

    all_types = ["All"] + run_query(
        "SELECT DISTINCT marker_type FROM markers WHERE marker_type IS NOT NULL ORDER BY marker_type"
    )["marker_type"].dropna().tolist()

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        gene_filter = st.selectbox("Locus", all_genes)
    with c2:
        type_filter = st.selectbox("Marker Type", all_types)
    with c3:
        search_term = st.text_input("Search term", placeholder="Marker name, allele, or sequence…")

    sql = """
        SELECT
            m.marker_name,
            m.target_gene,
            m.target_allele,
            m.marker_type,
            m.Chromosome,
            p.forward_primer_A,
            p.forward_primer_B,
            p.common_reverse_primer,
            p.snp_position,
            p.expected_allele_size_or_call,
            p.annealing_temp,
            p.pcr_profile,
            m.reference
        FROM markers m
        LEFT JOIN primers p ON m.marker_name = p.marker_name
        WHERE 1=1
    """
    params = []

    if gene_filter != "All":
        sql += " AND m.target_gene = ?"
        params.append(gene_filter)

    if type_filter != "All":
        sql += " AND m.marker_type = ?"
        params.append(type_filter)

    if search_term:
        escaped = search_term.replace("%", r"\%").replace("_", r"\_")
        term = f"%{escaped}%"
        sql += """
            AND (
                m.marker_name LIKE ? ESCAPE '\\'
                OR p.forward_primer_A LIKE ? ESCAPE '\\'
                OR p.forward_primer_B LIKE ? ESCAPE '\\'
                OR p.common_reverse_primer LIKE ? ESCAPE '\\'
                OR m.target_allele LIKE ? ESCAPE '\\'
            )
        """
        params.extend([term] * 5)

    results = run_query(sql, params)

    c_head, c_dl = st.columns([3, 1])
    with c_head:
        st.markdown(f"**Results:** {len(results)} markers found")
    with c_dl:
        st.download_button(
            "Export CSV",
            results.to_csv(index=False).encode("utf-8"),
            "bcmv_marker_search_results.csv",
            "text/csv",
            use_container_width=True
        )

    st.dataframe(results, use_container_width=True, hide_index=True, height=380)


# ============================================================
# 4. PRIMER MAP
# ============================================================
elif page == "Primer Map":
    st.title("Primer Map")

    try:
        import plotly.graph_objects as go
    except ImportError:
        st.error("Install Plotly with `pip install plotly` to use Primer Map.")
        st.stop()

    GC_TAIL_LONG = "GCGGGCAGGGCGGC"
    GC_TAIL_SHORT = "GCGGGC"
    FAM_TAIL = "GAAGGTGACCAAGTTCATGCT"
    HEX_TAIL = "GAAGGTCGGAGTCAACGGATT"

    def strip_primer_tail(primer_seq):
        seq = str(primer_seq).upper().replace(" ", "").strip()
        tails = [
            (GC_TAIL_LONG, "14-bp GC tail"),
            (GC_TAIL_SHORT, "6-bp GC tail"),
            (FAM_TAIL, "FAM tail"),
            (HEX_TAIL, "HEX tail"),
        ]
        for tail, label in tails:
            if seq.startswith(tail):
                return seq[len(tail):], f"{label} removed"
        return seq, "None"

    def reverse_complement(seq):
        comp = str.maketrans("ACGTNRYSWKM", "TGCANYRSWMK")
        return seq.translate(comp)[::-1]

    def map_primer(full_seq, sequence):
        core, tail_status = strip_primer_tail(full_seq)
        if not core:
            return None, None, "N/A", 0, tail_status, core

        rev = reverse_complement(core)
        fwd_hits = [m.start() for m in re.finditer(re.escape(core), sequence)]
        rev_hits = [m.start() for m in re.finditer(re.escape(rev), sequence)]

        if fwd_hits:
            s = fwd_hits[0]
            return s, s + len(core), "Sense (+)", len(fwd_hits), tail_status, core
        if rev_hits:
            s = rev_hits[0]
            return s, s + len(rev), "Antisense (-)", len(rev_hits), tail_status, core

        return None, None, "N/A", 0, tail_status, core

    seq_df = run_query("""
        SELECT sequence_id, target_gene, accession_or_locus_tag,
               sense_strand, fasta_sequence
        FROM sequences
    """)

    if seq_df.empty:
        st.info("No reference sequences found.")
    else:
        seq_options = {
            f"{r['target_gene']} · {r['accession_or_locus_tag']} · {r['sense_strand']}": r
            for _, r in seq_df.iterrows()
        }
        
        col_m1, col_m2 = st.columns([3, 1])
        with col_m1:
            selected = st.selectbox("Reference sequence", list(seq_options))
            seq_info = seq_options[selected]
        
        target_gene = seq_info["target_gene"]
        sequence = str(seq_info["fasta_sequence"]).upper().replace("\n", "").replace(" ", "")
        seq_len = len(sequence)

        with col_m2:
            st.metric("Sequence Length", f"{seq_len:,} bp")

        # Query markers and their corresponding alleles/calls
        primers = run_query("""
            SELECT m.marker_name, m.marker_type, m.target_allele, m.file_paths,
                   p.forward_primer_A, p.forward_primer_B,
                   p.common_reverse_primer, p.expected_allele_size_or_call
            FROM markers m
            LEFT JOIN primers p ON m.marker_name = p.marker_name
            WHERE m.target_gene = ?
            ORDER BY m.marker_name
        """, (target_gene,))

        if primers.empty:
            st.info(f"No markers registered for `{target_gene}`.")
        else:
            role_config = {
                "Forward Primer A": {"symbol": "▲", "color": COLOR_FWD_A},
                "Forward Primer B": {"symbol": "▲", "color": COLOR_FWD_B},
                "Common Reverse Primer": {"symbol": "▼", "color": COLOR_REV},
            }

            plot_rows, table_rows = [], []

            for _, row in primers.iterrows():
                # Extract allele info
                allele = row["target_allele"] if pd.notna(row["target_allele"]) else "N/A"
                allele_call = row["expected_allele_size_or_call"] if pd.notna(row["expected_allele_size_or_call"]) else "N/A"

                primer_set = {}
                for label, col in [
                    ("Forward Primer A", "forward_primer_A"),
                    ("Forward Primer B", "forward_primer_B"),
                    ("Common Reverse Primer", "common_reverse_primer"),
                ]:
                    value = row[col]
                    if pd.notna(value) and str(value).strip():
                        primer_set[label] = str(value)

                for label, full_seq in primer_set.items():
                    start, end, orientation, matches, tail, core = map_primer(full_seq, sequence)

                    status = "No match" if start is None else (
                        "Exact match" if matches == 1 else f"Multiple matches ({matches}×)"
                    )

                    table_rows.append({
                        "Marker": row["marker_name"],
                        "Target Allele": allele,
                        "Allele Call/Size": allele_call,
                        "Primer": label,
                        "Orientation": orientation,
                        "Start": start + 1 if start is not None else None,
                        "End": end,
                        "Matches": matches,
                        "Tail": tail,
                        "Status": status,
                    })

                    if start is not None:
                        plot_rows.append({
                            "marker": row["marker_name"],
                            "allele": allele,
                            "allele_call": allele_call,
                            "primer": label,
                            "start": start,
                            "end": end,
                            "orientation": orientation,
                            "matches": matches,
                        })

            result_df = pd.DataFrame(table_rows)

            # Build label for Y-axis containing marker and target allele
            marker_y_labels = {}
            for _, r in primers.iterrows():
                a_str = f" ({r['target_allele']})" if pd.notna(r['target_allele']) and str(r['target_allele']).strip() else ""
                marker_y_labels[r['marker_name']] = f"{r['marker_name']}{a_str}"

            y_axis_order = [marker_y_labels[m] for m in primers["marker_name"].unique()]

            if plot_rows:
                fig = go.Figure()

                # Draw track baselines
                for y_lbl in y_axis_order:
                    fig.add_trace(go.Scatter(
                        x=[0, seq_len],
                        y=[y_lbl, y_lbl],
                        mode="lines",
                        line=dict(width=6, color="#888888"),
                        opacity=0.25,
                        showlegend=False,
                        hoverinfo="skip",
                    ))

                # Draw colorblind-friendly primer segments with Allele display
                for label, config in role_config.items():
                    subset = [r for r in plot_rows if r["primer"] == label]
                    if not subset:
                        continue

                    for r in subset:
                        y_val = marker_y_labels[r["marker"]]
                        fig.add_trace(go.Scatter(
                            x=[r["start"], r["end"]],
                            y=[y_val, y_val],
                            mode="lines+markers",
                            line=dict(width=10, color=config["color"]),
                            marker=dict(size=8, color=config["color"]),
                            name=f"{config['symbol']} {label}",
                            legendgroup=label,
                            showlegend=not any(
                                x["primer"] == label
                                for x in plot_rows[:plot_rows.index(r)]
                            ),
                            hovertemplate=(
                                "<b>%{y}</b><br>"
                                f"<b>Primer:</b> {label}<br>"
                                f"<b>Allele Call:</b> {r['allele_call']}<br>"
                                f"<b>Position:</b> {r['start']+1:,}–{r['end']:,} bp<br>"
                                f"<b>Orientation:</b> {r['orientation']}<br>"
                                f"<b>Matches:</b> {r['matches']}<extra></extra>"
                            ),
                        ))

                fig.update_layout(
                    height=max(220, 45 * len(y_axis_order) + 80),
                    margin=dict(l=140, r=20, t=10, b=40),
                    xaxis_title="Genome Position (bp)",
                    yaxis_title=None,
                    yaxis=dict(
                        categoryorder="array",
                        categoryarray=y_axis_order,
                        autorange="reversed",
                    ),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    hovermode="closest",
                )
                st.plotly_chart(fig, use_container_width=True)

            # Tabbed interface for details and data table
            tab_insp, tab_data = st.tabs(["🔍 Marker Pattern Inspector", "📋 Mapping Data Table"])

            with tab_insp:
                c_sel, _ = st.columns([1, 2])
                with c_sel:
                    selected_marker = st.selectbox(
                        "Marker",
                        primers["marker_name"].unique().tolist(),
                        key="marker_inspect_select"
                    )

                marker_info = primers[primers["marker_name"] == selected_marker].iloc[0]
                img_path = marker_info.get("file_paths", None)

                c1, c2 = st.columns([1, 1])
                with c1:
                    st.markdown(f"**Amplification Pattern:** `{selected_marker}`")
                    if pd.notna(marker_info.get("target_allele")):
                        st.caption(f"**Target Allele:** {marker_info['target_allele']} | **Allele Call:** {marker_info.get('expected_allele_size_or_call', 'N/A')}")
                    if pd.notna(img_path) and str(img_path).strip() and os.path.exists(str(img_path).strip()):
                        st.image(str(img_path).strip(), caption=f"Assay pattern: {selected_marker}", use_container_width=True)
                    elif pd.notna(img_path) and str(img_path).strip():
                        st.warning(f"Image path registered (`{img_path}`), but file was not found on disk.")
                    else:
                        st.info("No amplification image registered for this marker.")

                with c2:
                    st.markdown("**Target Region Sequence**")
                    selected_rows = sorted(
                        [r for r in plot_rows if r["marker"] == selected_marker],
                        key=lambda r: r["start"]
                    )

                    if not selected_rows:
                        st.info("No mapped primers for this marker.")
                    else:
                        html = []
                        cursor = 0
                        for r in selected_rows:
                            html.append(f"<span style='font-family:monospace;color:#555;'>{sequence[cursor:r['start']]}</span>")
                            chunk = sequence[r["start"]:r["end"]]
                            html.append(f"<mark class='seq-highlight'>{chunk}</mark>")
                            cursor = max(cursor, r["end"])

                        html.append(f"<span style='font-family:monospace;color:#555;'>{sequence[cursor:]}</span>")

                        st.markdown(
                            "<div style='padding:10px;border:1px solid rgba(128,128,128,.2);' "
                            "border-radius:8px;word-break:break-all;max-height:260px; "
                            "overflow:auto;line-height:1.6;font-size:0.85rem;'>"
                            + "".join(html)
                            + "</div>",
                            unsafe_allow_html=True,
                        )

            with tab_data:
                st.dataframe(result_df, use_container_width=True, hide_index=True, height=260)


# ============================================================
# 5. FASTA VIEWER
# ============================================================
elif page == "FASTA Viewer":
    st.title("FASTA Viewer")

    seq_df = run_query("SELECT * FROM sequences")

    if seq_df.empty:
        st.info("No reference sequences found.")
    elif "fasta_sequence" not in seq_df.columns:
        st.error("The `sequences` table has no `fasta_sequence` column.")
    else:
        genes = sorted(seq_df["target_gene"].dropna().unique().tolist())
        
        c1, c2 = st.columns([1, 2])
        with c1:
            gene_pick = st.selectbox("Target Gene", ["All"] + genes)
            filtered = seq_df if gene_pick == "All" else seq_df[seq_df["target_gene"] == gene_pick]

        def sequence_label(row):
            acc = row.get("accession_or_locus_tag", row.get("sequence_id", "Unknown"))
            return f"{row.get('target_gene', '')} · {acc} · {row.get('sense_strand', '')}"

        labels = {sequence_label(r): idx for idx, r in filtered.iterrows()}

        if labels:
            with c2:
                selected = st.selectbox("Sequence Accession", list(labels))
            row = filtered.loc[labels[selected]]

            raw = str(row["fasta_sequence"]).upper().replace("\n", "").replace(" ", "")
            length = len(raw)
            gc = (raw.count("G") + raw.count("C")) / length * 100 if length else 0
            n_count = raw.count("N")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Length", f"{length:,} bp")
            c2.metric("GC Content", f"{gc:.1f}%")
            c3.metric("N Bases", f"{n_count:,}")
            c4.metric("Strand", str(row.get("sense_strand", "N/A")))

            acc = row.get("accession_or_locus_tag", row.get("sequence_id", "seq"))
            gene = row.get("target_gene", "gene")
            strand = row.get("sense_strand", "")
            header = f">{acc}_{gene}_{strand}".replace(" ", "_")
            wrapped = "\n".join(raw[i:i+60] for i in range(0, length, 60))
            fasta = f"{header}\n{wrapped}"

            st.download_button(
                "Download FASTA File",
                fasta,
                f"{acc}_{gene}.fasta".replace(" ", "_"),
                "text/plain",
            )
            
            # Constrained view box for full sequence text
            st.text_area("FASTA Record", fasta, height=220)

            with st.expander("Sequence Metadata"):
                st.dataframe(row.to_frame().T, use_container_width=True, hide_index=True)
        else:
            st.info("No sequences match this filter.")


# ============================================================
# 6. SQL CONSOLE
# ============================================================
elif page == "SQL Console":
    st.title("SQL Console")

    FORBIDDEN = {
        "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
        "REPLACE", "ATTACH", "DETACH", "PRAGMA", "VACUUM", "TRIGGER"
    }

    def is_safe_select(query):
        q = query.strip()
        if not q:
            return False, "Query is empty."
        if ";" in q.rstrip(";"):
            return False, "Only one SQL statement is allowed."
        upper = q.upper()
        if not (upper.startswith("SELECT") or upper.startswith("WITH")):
            return False, "Only SELECT / WITH queries are permitted."
        tokens = set(re.findall(r"[A-Za-z_]+", upper))
        blocked = FORBIDDEN.intersection(tokens)
        if blocked:
            return False, f"Forbidden keyword(s): {', '.join(sorted(blocked))}."
        return True, ""

    default_sql = """SELECT m.marker_name,
       m.target_gene,
       p.forward_primer_A,
       p.common_reverse_primer,
       p.annealing_temp
FROM markers m
JOIN primers p ON m.marker_name = p.marker_name
WHERE m.target_gene = 'I gene'"""

    query = st.text_area("SQL Query (Read-Only)", default_sql, height=120)

    if st.button("Run Query", type="primary"):
        ok, msg = is_safe_select(query)
        if not ok:
            st.error(msg)
        else:
            try:
                with sqlite3.connect(f"file:{DB_NAME}?mode=ro", uri=True) as conn:
                    result = pd.read_sql_query(query, conn)

                st.success(f"{len(result)} rows returned.")
                st.dataframe(result, use_container_width=True, hide_index=True, height=280)

                st.download_button(
                    "Export Results (CSV)",
                    result.to_csv(index=False).encode("utf-8"),
                    "query_results.csv",
                    "text/csv",
                )
            except Exception as e:
                st.error(f"SQL execution error: {e}")