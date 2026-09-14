# ============================================================
# BCMV / BCMNV RESISTANCE MARKER DATABASE
# Accessible & Space-Optimized Streamlit UI
# ============================================================

import os
import re
import time
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

DB_NAME = "bcmv_markers.db"
APP_DIR = Path(__file__).resolve().parent
ANNOTATIONS_DIR = APP_DIR / "static/annotations"

st.set_page_config(
    page_title="Bean resistance Genomics",
    page_icon="🫘",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Colorblind-Safe Color Palette (Okabe-Ito Inspired) ----------
COLOR_FWD_A = "#0072B2"  # Blue          -> Forward Primer A
COLOR_FWD_B = "#D55E00"  # Vermilion     -> Forward Primer B
COLOR_REV   = "#009E73"  # Bluish Green  -> Common Reverse Primer
COLOR_ACCENT= "#CC79A7"  # Reddish Purple -> "Multiple matches" status

COLOR_FWD_B_TEXT  = "#C05500"  # 4.6:1 on white
COLOR_REV_TEXT    = "#007E5C"  # 5.1:1 on white
COLOR_ACCENT_TEXT = "#A36186"  # 4.6:1 on white

# ---------- Gene-model track palette (Primer Map plot) ----------
GENE_BACKBONE     = "#555555"
GENE_INTRON       = "#333333"
GENE_EXON_FILL    = "#8092A3"
GENE_EXON_BORDER  = "#1E252B"
GENE_CDS_FILL     = "#2C3E50"
GENE_CDS_BORDER   = "#0F171E"
GENE_UTR_FILL     = "#5D6D7E"
GENE_UTR_BORDER   = "#1E252B"

PLOT_TEXT_COLOR   = "#111111"
PLOT_PANEL_BG     = "#FFFFFF"

# ---------- Accessible & Compact CSS ----------
st.markdown(f"""
<style>
    .block-container {{
        max-width: 1450px;
        padding-top: 1.2rem;
        padding-bottom: 1.5rem;
    }}

    #MainMenu, footer {{ visibility: hidden; }}

    section[data-testid="stSidebar"] {{
        border-right: 1px solid rgba(128,128,128,.2);
    }}

    div[data-testid="stMetric"] {{
        background: rgba(128,128,128,.06);
        border: 1px solid rgba(128,128,128,.25);
        padding: .5rem .8rem;
        border-radius: 8px;
    }}

    .muted {{ opacity: .75; font-weight: 500; }}

    div[data-testid="stDataFrame"] {{
        border-radius: 8px;
        border: 1px solid rgba(128,128,128,.2);
    }}

    div[data-testid="stVerticalBlock"] > div {{
        gap: .45rem;
    }}

    mark.seq-highlight {{
        background-color: #FFEA80;
        color: #000000;
        padding: 2px 4px;
        border-radius: 3px;
        border-bottom: 2px solid {COLOR_FWD_A};
        font-weight: bold;
    }}

    .chip {{
        display: inline-block;
        background: rgba(0,114,178,.08);
        color: {COLOR_FWD_A};
        padding: 2px 10px;
        border-radius: 999px;
        font-size: .78rem;
        font-weight: 600;
        margin-right: 6px;
    }}
</style>
""", unsafe_allow_html=True)


# ---------- Database helpers ----------
@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def run_query(query, params=()):
    df = pd.read_sql_query(query, get_connection(), params=tuple(params))
    
    # Fix PyArrow mixed-type serialization error
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).replace({"nan": None, "None": None, "<NA>": None})
    return df


def safe_count(table_name):
    try:
        return int(run_query(
            f"SELECT COUNT(*) AS count FROM {table_name}"
        )["count"].iloc[0])
    except Exception:
        return None


def get_table_schema(table_name):
    try:
        info = run_query(f"PRAGMA table_info({table_name})")
        return info[["name", "type", "notnull", "pk"]].rename(columns={
            "name": "Column", "type": "Type", "notnull": "Required", "pk": "Primary Key"
        })
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


def go_to(page_name, **extra_state):
    def _callback():
        st.session_state.nav_page = page_name
        for key, value in extra_state.items():
            st.session_state[key] = value
    return _callback


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
PAGE_ICONS = {
    "Overview": "🏠",
    "Loci Browser": "🧬",
    "Marker Search": "🔍",
    "Primer Map": "🗺️",
    "FASTA Viewer": "📄",
    "SQL Console": "💻",
}
PAGE_HELP = {
    "Overview": "Database summary and raw table browser.",
    "Loci Browser": "Explore resistance genes and their linked markers.",
    "Marker Search": "Filter and search diagnostic markers.",
    "Primer Map": "Visualize where primers map on a reference sequence.",
    "FASTA Viewer": "Inspect and download reference sequences.",
    "SQL Console": "Run your own read-only SQL queries.",
}

if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Overview"

with st.sidebar:
    st.markdown("## 🫘 Bean Genomics")
    st.caption("Phaseolus vulgaris L.")
    page = st.radio(
        "MODULE",
        list(PAGE_ICONS.keys()),
        format_func=lambda p: f"{PAGE_ICONS[p]}  {p}",
        key="nav_page",
    )
    st.caption(PAGE_HELP[page])

    st.divider()
    st.caption("Database: `bcmv_markers.db`")


# ============================================================
# 1. OVERVIEW
# ============================================================
if page == "Overview":
    st.title("BCMV / BCMNV Resistance Genomics")
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

    with st.expander("👋 New here? Quick guide", expanded=False):
        st.markdown(
            "- **Loci Browser** — pick a resistance gene and see its markers.\n"
            "- **Marker Search** — filter markers by gene, assay type, or free text.\n"
            "- **Primer Map** — see exactly where primers map on a reference sequence.\n"
            "- **FASTA Viewer** — inspect and download reference sequences.\n"
            "- **SQL Console** — run your own read-only queries, with a schema reference."
        )
        c1, c2, c3 = st.columns(3)
        c1.button("🧬 Browse loci", use_container_width="stretch", on_click=go_to("Loci Browser"))
        c2.button("🔍 Search markers", use_container_width="stretch", on_click=go_to("Marker Search"))
        c3.button("💻 Open SQL console", use_container_width="stretch", on_click=go_to("SQL Console"))

    st.markdown("<br>", unsafe_allow_html=True)
    with st.expander("📁 Browse Raw Database Tables", expanded=True):
        tabs = st.tabs(["Genes", "Markers", "Primers", "Sequences"])
        for tab, table in zip(tabs, ["genes", "markers", "primers", "sequences"]):
            with tab:
                df = run_query(f"SELECT * FROM {table}")
                
                # Link Configurations
                column_config = {}
                if "Uniprot_database" in df.columns:
                    column_config["Uniprot_database"] = st.column_config.LinkColumn(
                        "UniProt Entry",
                        display_text="Open UniProt 🔗",
                        help="Click to open UniProt record",
                    )
                if "link_publication" in df.columns:
                    column_config["link_publication"] = st.column_config.LinkColumn(
                        "Publication Link",
                        display_text="Open Article 🔗",
                        help="Click to view publication",
                    )

                st.dataframe(
                    df,
                    use_container_width="stretch",
                    hide_index=True,
                    height=300,
                    column_config=column_config,
                )


# ============================================================
# 2. LOCI BROWSER
# ============================================================
elif page == "Loci Browser":
    st.title("Loci Browser")

    # Aggregate candidate annotations directly from genes table
    genes_df = run_query("""
        SELECT 
            gene_name,
            gene_symbol,
            chromosome,
            description,
            GROUP_CONCAT(DISTINCT candidate_gene_annotation) AS candidate_gene_annotation
        FROM genes
        GROUP BY gene_name
        ORDER BY gene_id ASC
    """)

    if genes_df.empty:
        st.info("No genes found in the database.")
    else:
        # Format raw candidate annotations
        genes_df["candidate_gene_annotation"] = (
            genes_df["candidate_gene_annotation"]
            .astype(str)
            .str.replace(",", " | ")
            .replace({"None": "N/A", "nan": "N/A", "<NA>": "N/A"})
        )

        gene_names = genes_df["gene_name"].dropna().tolist()

        default_idx = 0
        hint = st.session_state.pop("loci_browser_gene_hint", None)
        if hint and hint in gene_names:
            default_idx = gene_names.index(hint)

        c_sel, _ = st.columns([1, 2])
        with c_sel:
            selected_gene = st.selectbox(
                "Target locus", gene_names, index=default_idx,
                help="Start typing to filter the list of resistance loci.",
            )

        gene_info = genes_df.loc[genes_df["gene_name"] == selected_gene].iloc[0]

        st.markdown(
            f"### `{gene_info['gene_symbol']}` <span class='muted'>({gene_info['gene_name']})</span>",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns([0.5, 2.5])
        c1.metric("Chromosome", gene_info["chromosome"])
        c2.metric("Candidate Annotation", gene_info["candidate_gene_annotation"])

        # Fetch markers linked to this locus
        markers_query = """
            SELECT
                m.marker_name,
                m.target_allele,
                m.marker_type,
                m.Chromosome,
                p.snp_position,
                m.reference,
                m.link_publication
            FROM markers m
            LEFT JOIN primers p ON m.marker_name = p.marker_name
            WHERE m.target_gene = ?
        """
        associated = run_query(markers_query, (selected_gene,))

        section(f"Associated Markers ({len(associated)})", "Diagnostic assays linked to this locus.")

        if associated.empty:
            st.info("No diagnostic markers have been registered for this locus yet.")
        else:

            st.dataframe(
                associated,
                use_container_width="stretch",
                hide_index=True,
                height=280,
                column_config={
                    "candidate_gene_annotation": st.column_config.TextColumn(
                        "Candidate Gene Annotation",
                        help="Original candidate gene annotation from genes.csv",
                    ),
                    "link_publication": st.column_config.LinkColumn(
                        "Publication Link",
                        display_text="Open Article 🔗",
                        help="Click to view the publication",
                    ),
                },
            )

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

    def _reset_marker_filters():
        st.session_state.ms_gene = "All"
        st.session_state.ms_type = "All"
        st.session_state.ms_search = ""

    c1, c2, c3, c4 = st.columns([1, 1, 2, 0.6])
    with c1:
        gene_filter = st.selectbox(
            "Locus", all_genes, key="ms_gene", help="Filter by resistance locus."
        )
    with c2:
        type_filter = st.selectbox(
            "Marker Type", all_types, key="ms_type",
            help="Filter by assay/marker type (e.g. SCAR, CAPS, KASP).",
        )
    with c3:
        search_term = st.text_input(
            "Search term", placeholder="Marker name, allele, or sequence…", key="ms_search",
            help="Matches marker name, primer sequences, or target allele.",
        )
    with c4:
        st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
        st.button(
            "Reset", use_container_width="stretch", help="Clear all filters",
            on_click=_reset_marker_filters,
        )

    sql = """
        SELECT
            m.marker_name,
            m.target_gene,
            m.target_allele,
            m.marker_type,
            m.Chromosome,
            p.snp_position,
            p.forward_primer_A,
            p.forward_primer_B,
            p.common_reverse_primer,
            p.annealing_temp,
            p.pcr_profile
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

    chips = []
    if gene_filter != "All":
        chips.append(f"<span class='chip'>Locus: {gene_filter}</span>")
    if type_filter != "All":
        chips.append(f"<span class='chip'>Type: {type_filter}</span>")
    if search_term:
        chips.append(f"<span class='chip'>Text: “{search_term}”</span>")

    c_head, c_sort, c_dl = st.columns([2.4, 1, 1])
    with c_head:
        st.markdown(f"**Results:** {len(results)} markers found")
        if chips:
            st.markdown(" ".join(chips), unsafe_allow_html=True)
    with c_sort:
        sort_col = st.selectbox(
            "Sort by",
            ["marker_name", "target_gene", "marker_type"],
            format_func=lambda c: {"marker_name": "Marker", "target_gene": "Locus", "marker_type": "Type"}[c],
            label_visibility="collapsed",
            disabled=results.empty,
        )
    with c_dl:
        st.download_button(
            "Export CSV",
            results.to_csv(index=False).encode("utf-8"),
            "bcmv_marker_search_results.csv",
            "text/csv",
            use_container_width="stretch",
            disabled=results.empty,
        )

    if results.empty:
        st.info("No markers matched these filters. Try broadening your search or clearing filters.")
    else:
        if sort_col in results.columns:
            results = results.sort_values(sort_col, na_position="last")
        st.dataframe(results, use_container_width="stretch", hide_index=True, height=380)


# ============================================================
# 4. PRIMER MAP
# ============================================================
elif page == "Primer Map":
    st.title("Primer Map")
    st.caption("Select an amplicon to view its complete primer arrangement on the reference sequence.")

    try:
        import plotly.graph_objects as go
    except ImportError:
        st.error("Install Plotly with `pip install plotly` to use Primer Map.")
        st.stop()

    GC_TAIL_LONG = "GCGGGCAGGGCGGC"
    GC_TAIL_SHORT = "GCGGGC"
    FAM_TAIL = "[FAM]" #GAAGGTGACCAAGTTCATGCT
    HEX_TAIL = "[HEX]" #GAAGGTCGGAGTCAACGGATT

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
        comp = str.maketrans("ACGTNRYSWKMBDHV", "TGCANYRSWMKVHDB")
        return seq.translate(comp)[::-1]

    def _parse_gff_attributes(attr_text):
        attrs = {}
        for item in str(attr_text).strip().split(";"):
            if not item or "=" not in item:
                continue
            key, value = item.split("=", 1)
            attrs[key.strip()] = value.strip()
        return attrs

    def load_gene_annotation(gene_name, sequence_length, accession_or_locus_tag=None, reference_genome=None, sense_strand=None, location=None):
        if not ANNOTATIONS_DIR.exists():
            return None

        metadata_strand = None
        for value in (sense_strand, location):
            if value is None or pd.isna(value):
                continue
            text = str(value).strip().lower()
            if re.search(r"\breverse\b|\bantisense\b|\bminus\b|\(-\)", text):
                metadata_strand = "-"
                break
            if re.search(r"\bforward\b|\bsense\b|\bplus\b|\(\+\)", text):
                metadata_strand = "+"
                break

        identifiers = []
        for value in [accession_or_locus_tag, gene_name, reference_genome]:
            if value is None or pd.isna(value):
                continue
            value = str(value).strip()
            if value and value not in identifiers:
                identifiers.append(value)

        candidates = []
        for ident in identifiers:
            candidates.extend([
                ANNOTATIONS_DIR / f"{ident}.gff",
                ANNOTATIONS_DIR / f"{ident}.gff3",
                ANNOTATIONS_DIR / f"{ident}.GFF",
                ANNOTATIONS_DIR / f"{ident}.GFF3",
            ])

        gff_path = next((p for p in candidates if p.is_file()), None)

        if gff_path is None:
            gff_files = sorted(list(ANNOTATIONS_DIR.glob("*.gff")) + list(ANNOTATIONS_DIR.glob("*.gff3")) +
                               list(ANNOTATIONS_DIR.glob("*.GFF")) + list(ANNOTATIONS_DIR.glob("*.GFF3")))
            identifier_set = {x.lower() for x in identifiers}
            for candidate in gff_files:
                try:
                    with candidate.open("r", encoding="utf-8") as fh:
                        for raw in fh:
                            if raw.startswith("#"):
                                continue
                            fields = raw.rstrip("\n").split("\t")
                            if len(fields) != 9:
                                continue
                            seqid, _, feature_type, _, _, _, _, _, attrs = fields
                            parsed = _parse_gff_attributes(attrs)
                            values = {
                                str(seqid).strip().lower(),
                                str(parsed.get("Name", "")).strip().lower(),
                                str(parsed.get("ID", "")).strip().lower(),
                            }
                            if identifier_set.intersection(values):
                                gff_path = candidate
                                break
                        if gff_path is not None:
                            break
                except OSError:
                    continue

        if gff_path is None:
            return None

        features = []
        gene_feature = None
        try:
            with gff_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    fields = line.split("\t")
                    if len(fields) != 9:
                        continue
                    seqid, source, feature_type, start, end, score, strand, phase, attrs = fields
                    try:
                        start_i = int(start)
                        end_i = int(end)
                    except ValueError:
                        continue
                    parsed = _parse_gff_attributes(attrs)
                    record = {
                        "seqid": seqid,
                        "type": feature_type.lower(),
                        "start": start_i,
                        "end": end_i,
                        "strand": strand,
                        "attrs": parsed,
                    }
                    if feature_type.lower() == "gene":
                        gene_feature = record
                    elif feature_type.lower() in {
                        "exon", "cds", "five_prime_utr", "three_prime_utr",
                        "5utr", "3utr", "utr"
                    }:
                        features.append(record)
        except OSError:
            return None

        if gene_feature is None and features:
            gene_feature = {
                "start": min(f["start"] for f in features),
                "end": max(f["end"] for f in features),
                "strand": features[0]["strand"],
                "seqid": features[0]["seqid"],
                "attrs": {},
            }

        if gene_feature is None or not features:
            return None

        groups = {}
        for f in features:
            parent = (f["attrs"].get("Parent") or
                      f["attrs"].get("transcript_id") or
                      "__ungrouped__")
            groups.setdefault(parent, []).append(f)

        best_parent, best_features = max(
            groups.items(),
            key=lambda kv: (
                max(x["end"] for x in kv[1]) - min(x["start"] for x in kv[1]),
                sum(x["end"] - x["start"] + 1 for x in kv[1]),
                len(kv[1]),
            ),
        )

        explicit_exons = [f for f in best_features if f["type"] == "exon"]
        exon_source = explicit_exons if explicit_exons else best_features
        segments = sorted((f["start"], f["end"]) for f in exon_source)

        merged = []
        for start_i, end_i in segments:
            if not merged or start_i > merged[-1][1] + 1:
                merged.append([start_i, end_i])
            else:
                merged[-1][1] = max(merged[-1][1], end_i)

        gene_start = gene_feature["start"]
        gene_end = gene_feature["end"]
        gene_span = gene_end - gene_start + 1
        offset = gene_start - 1 if gene_start > 1 else 0

        def relative_interval(start_i, end_i):
            rel_start = start_i - 1 - offset
            rel_end = end_i - offset
            if rel_end <= 0 or rel_start >= sequence_length:
                return None
            rel_start = max(0, rel_start)
            rel_end = min(sequence_length, rel_end)
            if rel_end <= rel_start:
                return None
            return rel_start, rel_end

        if metadata_strand == "-":
            def orient_interval(interval):
                if interval is None:
                    return None
                rel_start, rel_end = interval
                return sequence_length - rel_end, sequence_length - rel_start
        else:
            def orient_interval(interval):
                return interval

        plot_strand = metadata_strand or gene_feature["strand"]

        oriented_exons = []
        for start_i, end_i in merged:
            interval = orient_interval(relative_interval(start_i, end_i))
            if interval:
                rel_start, rel_end = interval
                oriented_exons.append({
                    "start": rel_start,
                    "end": rel_end,
                    "length": rel_end - rel_start,
                })

        oriented_exons.sort(key=lambda x: (x["start"], x["end"]))
        n_exons = len(oriented_exons)
        exon_rows = []
        for display_idx, exon in enumerate(oriented_exons):
            exon_number = (n_exons - display_idx) if plot_strand == "-" else (display_idx + 1)
            exon_rows.append({
                "exon": exon_number,
                "start": exon["start"],
                "end": exon["end"],
                "length": exon["length"],
            })

        cds_rows = []
        utr_rows = []
        for f in best_features:
            interval = orient_interval(relative_interval(f["start"], f["end"]))
            if not interval:
                continue
            rel_start, rel_end = interval
            row = {
                "start": rel_start,
                "end": rel_end,
                "length": rel_end - rel_start,
                "type": f["type"],
            }
            if f["type"] == "cds":
                cds_rows.append(row)
            elif f["type"] in {"five_prime_utr", "three_prime_utr", "5utr", "3utr", "utr"}:
                utr_rows.append(row)

        return {
            "path": gff_path,
            "gene_start": gene_start,
            "gene_end": gene_end,
            "gene_span": gene_span,
            "strand": plot_strand,
            "metadata_strand": metadata_strand,
            "sense_strand": sense_strand,
            "location": location,
            "transcript": best_parent,
            "exons": exon_rows,
            "cds": cds_rows,
            "utrs": utr_rows,
        }

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

    try:
        seq_schema = run_query("PRAGMA table_info(sequences)")
        seq_columns = set(seq_schema["name"].astype(str).tolist()) if not seq_schema.empty else set()
    except Exception:
        seq_columns = set()

    def _pick_column(*names):
        for name in names:
            if name in seq_columns:
                return name
        return None

    sense_col = _pick_column("Sense_strand", "sense_strand", "Sense Strand", "sense")
    location_col = _pick_column("Location", "location", "LOCATION", "Genomic_location", "genomic_location")

    required_seq_cols = [
        "sequence_id", "target_gene", "Reference_genome",
        "accession_or_locus_tag", "Genomic_sequence"
    ]
    missing_seq_cols = [c for c in required_seq_cols if c not in seq_columns]

    if missing_seq_cols:
        st.error(
            "The `sequences` table is missing required column(s): "
            + ", ".join(f"`{c}`" for c in missing_seq_cols)
        )
        seq_df = pd.DataFrame()
    else:
        sense_sql = f'"{sense_col}" AS sense_strand' if sense_col else "'' AS sense_strand"
        location_sql = f'"{location_col}" AS location' if location_col else "'' AS location"

        seq_df = run_query(f"""
            SELECT sequence_id, target_gene, Reference_genome, accession_or_locus_tag,
                   {sense_sql}, {location_sql}, Genomic_sequence
            FROM sequences
        """)

        if location_col is None:
            st.caption(
                "ℹ️ This database does not contain a `Location` column. "
                "Exon orientation is therefore determined from `Sense_strand`."
            )

    if seq_df.empty:
        st.info("No reference sequences found.")
    else:
        seq_df = seq_df.copy()
        seq_df["_label"] = (
            seq_df["target_gene"].astype(str) + " · "
            + seq_df["Reference_genome"].astype(str) + " · "
            + seq_df["accession_or_locus_tag"].astype(str) + " · "
            + seq_df["sense_strand"].astype(str)
        )
        dup_mask = seq_df["_label"].duplicated(keep=False)
        if dup_mask.any():
            seq_df.loc[dup_mask, "_label"] = (
                seq_df.loc[dup_mask, "_label"] + " (id "
                + seq_df.loc[dup_mask, "sequence_id"].astype(str) + ")"
            )

        seq_options = {row["_label"]: row for _, row in seq_df.iterrows()}
        option_labels = list(seq_options.keys())

        default_idx = 0
        hint = st.session_state.pop("primer_map_gene_hint", None)
        if hint:
            for i, lbl in enumerate(option_labels):
                if seq_options[lbl]["target_gene"] == hint:
                    default_idx = i
                    break

        col_m1, col_m2 = st.columns([3, 1])
        with col_m1:
            selected = st.selectbox(
                "Reference sequence", option_labels, index=default_idx,
                help="Choose the reference sequence used to map the marker primers.",
            )
            seq_info = seq_options[selected]

        target_gene = seq_info["target_gene"]
        sequence = str(seq_info["Genomic_sequence"]).upper().replace("\n", "").replace(" ", "")
        seq_len = len(sequence)

        with col_m2:
            st.metric("Sequence Length", f"{seq_len:,} bp")

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
                "Forward Primer A": {"symbol": "▶", "color": COLOR_FWD_A, "short": "Fa"},
                "Forward Primer B": {"symbol": "▶", "color": COLOR_FWD_B, "short": "Fb"},
                "Common Reverse Primer": {"symbol": "◀", "color": COLOR_REV, "short": "R"},
            }

            plot_rows, table_rows, amplicons = [], [], []

            for _, row in primers.iterrows():
                marker = str(row["marker_name"])
                allele = row["target_allele"] if pd.notna(row["target_allele"]) else "N/A"
                allele_call = row["expected_allele_size_or_call"] if pd.notna(row["expected_allele_size_or_call"]) else "N/A"

                mapped = {}
                for label, col in [
                    ("Forward Primer A", "forward_primer_A"),
                    ("Forward Primer B", "forward_primer_B"),
                    ("Common Reverse Primer", "common_reverse_primer"),
                ]:
                    value = row[col]

                    value_text = "" if pd.isna(value) else str(value).strip()
                    missing_primer_values = {
                        "", "N/A", "NA", "N.A.", "NONE", "NULL", "-", "—"
                    }

                    if value_text.upper() not in missing_primer_values:
                        value = value_text
                        start, end, orientation, matches, tail, core = map_primer(value, sequence)
                        mapped[label] = {
                            "start": start, "end": end, "orientation": orientation,
                            "matches": matches, "tail": tail, "core": core,
                        }

                        status = "No match" if start is None else (
                            "Exact match" if matches == 1 else f"Multiple matches ({matches}×)"
                        )
                        table_rows.append({
                            "Marker": marker,
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
                                "marker": marker, "allele": allele, "allele_call": allele_call,
                                "primer": label, "start": start, "end": end,
                                "orientation": orientation, "matches": matches,
                            })

                reverse = mapped.get("Common Reverse Primer")
                if reverse and reverse["start"] is not None:
                    for fwd_label in ["Forward Primer A", "Forward Primer B"]:
                        fwd = mapped.get(fwd_label)
                        if not fwd or fwd["start"] is None:
                            continue

                        amp_start = min(fwd["start"], reverse["start"])
                        amp_end = max(fwd["end"], reverse["end"])
                        amp_size = amp_end - amp_start

                        amplicons.append({
                            "marker": marker,
                            "allele": allele,
                            "allele_call": allele_call,
                            "forward": fwd_label,
                            "amp_start": amp_start,
                            "amp_end": amp_end,
                            "amp_size": amp_size,
                            "forward_start": fwd["start"],
                            "forward_end": fwd["end"],
                            "reverse_start": reverse["start"],
                            "reverse_end": reverse["end"],
                        })

            result_df = pd.DataFrame(table_rows)

            if amplicons:
                amp_options = []
                for i, amp in enumerate(amplicons):
                    call = str(amp["allele_call"])
                    allele_text = "" if amp["allele"] == "N/A" else f" | allele {amp['allele']}"
                    amp_options.append(
                        f"{amp['marker']} | {amp['forward'].replace('Forward Primer ', 'F-')} | "
                        f"{amp['amp_size']:,} bp{allele_text} | {call}"
                    )

                selected_amp_label = st.selectbox(
                    "Select amplicon",
                    amp_options,
                    key="primer_map_amplicon_select",
                    help="Select a complete PCR assay. The selection controls the map and assay details below.",
                )
                selected_amp = amplicons[amp_options.index(selected_amp_label)]

                marker_info = primers[primers["marker_name"] == selected_amp["marker"]].iloc[0]
                img_path = marker_info.get("file_paths", None)

                c1, c2, c3, c4 = st.columns([1.5, 1.2, 1, 1.2])
                c1.metric("Marker", selected_amp["marker"])
                c2.metric("Reference genome", seq_info["Reference_genome"])
                c3.metric("Amplicon", f"{selected_amp['amp_size']:,} bp")
                c4.metric("Target allele", str(selected_amp["allele"]))

                annotation = load_gene_annotation(
                    target_gene,
                    seq_len,
                    accession_or_locus_tag=seq_info.get("accession_or_locus_tag"),
                    reference_genome=seq_info.get("Reference_genome"),
                    sense_strand=seq_info.get("sense_strand"),
                    location=seq_info.get("location"),
                )

                fig = go.Figure()

                fig.add_trace(go.Scatter(
                    x=[0, seq_len], y=[0, 0], mode="lines",
                    line=dict(width=6, color=GENE_BACKBONE), opacity=0.35,
                    showlegend=False, hoverinfo="skip",
                ))

                gene_y = -0.48
                exon_half = 0.13

                if annotation and annotation["exons"]:
                    exons = annotation["exons"]

                    for left, right in zip(exons[:-1], exons[1:]):
                        fig.add_trace(go.Scatter(
                            x=[left["end"], right["start"]],
                            y=[gene_y, gene_y],
                            mode="lines",
                            line=dict(width=2, color=GENE_INTRON),
                            showlegend=False,
                            hoverinfo="skip",
                        ))

                    for exon in exons:
                        fig.add_shape(
                            type="rect",
                            x0=exon["start"], x1=exon["end"],
                            y0=gene_y - exon_half, y1=gene_y + exon_half,
                            line=dict(width=1.5, color=GENE_EXON_BORDER),
                            fillcolor=GENE_EXON_FILL,
                            layer="above",
                        )

                        fig.add_annotation(
                            x=(exon["start"] + exon["end"]) / 2,
                            y=gene_y + 0.19,
                            text=f"<b>E{exon['exon']}</b>",
                            showarrow=False,
                            font=dict(size=11, color=PLOT_TEXT_COLOR),
                            xanchor="center",
                            yanchor="bottom",
                        )

                        fig.add_trace(go.Scatter(
                            x=[(exon["start"] + exon["end"]) / 2],
                            y=[gene_y],
                            mode="markers",
                            marker=dict(size=18, color=GENE_EXON_FILL, opacity=0),
                            showlegend=False,
                            hovertemplate=(
                                f"<b>Exon {exon['exon']}</b><br>"
                                f"Position: {exon['start'] + 1:,}–{exon['end']:,} bp<br>"
                                f"Length: {exon['length']:,} bp<extra></extra>"
                            ),
                        ))

                    for cds in annotation["cds"]:
                        fig.add_shape(
                            type="rect",
                            x0=cds["start"], x1=cds["end"],
                            y0=gene_y - 0.075, y1=gene_y + 0.075,
                            line=dict(width=1, color=GENE_CDS_BORDER),
                            fillcolor=GENE_CDS_FILL,
                            layer="above",
                        )

                    for utr in annotation.get("utrs", []):
                        fig.add_shape(
                            type="rect",
                            x0=utr["start"], x1=utr["end"],
                            y0=gene_y - 0.075, y1=gene_y + 0.075,
                            line=dict(width=1, color=GENE_UTR_BORDER),
                            fillcolor=GENE_UTR_FILL,
                            layer="above",
                        )

                    fig.add_trace(go.Scatter(
                        x=[None], y=[None], mode="markers",
                        marker=dict(size=12, symbol="square", color=GENE_EXON_FILL,
                                    line=dict(width=1, color=GENE_EXON_BORDER)),
                        name="Exon",
                        hoverinfo="skip",
                    ))
                    fig.add_trace(go.Scatter(
                        x=[None], y=[None], mode="markers",
                        marker=dict(size=12, symbol="square", color=GENE_CDS_FILL,
                                    line=dict(width=1, color=GENE_CDS_BORDER)),
                        name="CDS",
                        hoverinfo="skip",
                    ))
                    if annotation.get("utrs"):
                        fig.add_trace(go.Scatter(
                            x=[None], y=[None], mode="markers",
                            marker=dict(size=12, symbol="square", color=GENE_UTR_FILL,
                                        line=dict(width=1, color=GENE_UTR_BORDER)),
                            name="UTR",
                            hoverinfo="skip",
                        ))

                fwd_cfg = role_config[selected_amp["forward"]]
                amp_color = fwd_cfg["color"]
                amp_y = 0.62

                fig.add_trace(go.Scatter(
                    x=[selected_amp["amp_start"], selected_amp["amp_end"]],
                    y=[amp_y, amp_y],
                    mode="lines",
                    line=dict(width=26, color=amp_color),
                    opacity=0.28,
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{selected_amp['marker']}</b><br>"
                        f"Amplicon: {selected_amp['amp_size']:,} bp<br>"
                        f"Target allele: {selected_amp['allele']}<br>"
                        f"Allele call/size: {selected_amp['allele_call']}<br>"
                        f"Coordinates: {selected_amp['amp_start'] + 1:,}–{selected_amp['amp_end']:,} bp"
                        "<extra></extra>"
                    ),
                ))

                center = (selected_amp["amp_start"] + selected_amp["amp_end"]) / 2
                fig.add_annotation(
                    x=center, y=amp_y + 0.18,
                    text=(f"<b>{selected_amp['marker']}</b><br>"
                          f"<b>{selected_amp['amp_size']:,} bp amplicon</b>"),
                    showarrow=False,
                    xanchor="center", yanchor="bottom",
                    bgcolor="#FFFFFF",
                    bordercolor=amp_color,
                    borderwidth=2,
                    borderpad=5,
                    font=dict(size=12, color=amp_color),
                )

                fig.add_trace(go.Scatter(
                    x=[selected_amp["forward_start"]], y=[amp_y],
                    mode="markers+text",
                    marker=dict(size=14, color=amp_color, symbol="triangle-right"),
                    text=[f"<b>{fwd_cfg['symbol']} {fwd_cfg['short']}</b>"],
                    textposition="bottom center",
                    textfont=dict(size=12, color=PLOT_TEXT_COLOR),
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{selected_amp['marker']}</b><br>"
                        f"{fwd_cfg['short']} · {selected_amp['forward']}<br>"
                        f"Position: {selected_amp['forward_start'] + 1:,}–{selected_amp['forward_end']:,} bp"
                        "<extra></extra>"
                    ),
                ))

                rev_cfg = role_config["Common Reverse Primer"]
                fig.add_trace(go.Scatter(
                    x=[selected_amp["reverse_start"]], y=[amp_y],
                    mode="markers+text",
                    marker=dict(size=14, color=rev_cfg["color"], symbol="triangle-left"),
                    text=[f"<b>{rev_cfg['symbol']} {rev_cfg['short']}</b>"],
                    textposition="bottom center",
                    textfont=dict(size=12, color=PLOT_TEXT_COLOR),
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{selected_amp['marker']}</b><br>"
                        "R · Common reverse primer<br>"
                        f"Position: {selected_amp['reverse_start'] + 1:,}–{selected_amp['reverse_end']:,} bp"
                        "<extra></extra>"
                    ),
                ))

                fig.add_annotation(
                    x=seq_len / 2, y=-0.84,
                    text=f"<b>{target_gene}</b> · {seq_info['Reference_genome']} · {seq_len:,} bp",
                    showarrow=False,
                    xanchor="center", yanchor="top",
                    font=dict(size=12, color=PLOT_TEXT_COLOR),
                )

                fig.update_layout(
                    height=470,
                    margin=dict(l=70, r=30, t=75, b=90),
                    xaxis_title="Reference sequence position (bp)",
                    font=dict(color=PLOT_TEXT_COLOR),
                    yaxis=dict(visible=False, range=[-1.05, 1.15]),
                    xaxis=dict(
                        showgrid=True,
                        zeroline=False,
                        gridcolor="#E2E8F0",
                        tickfont=dict(color=PLOT_TEXT_COLOR, size=11),
                        title_font=dict(color=PLOT_TEXT_COLOR, size=13),
                    ),
                    plot_bgcolor=PLOT_PANEL_BG,
                    paper_bgcolor=PLOT_PANEL_BG,
                    hovermode="closest",
                    showlegend=bool(annotation and annotation["exons"]),
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1,
                        font=dict(color=PLOT_TEXT_COLOR),
                    ),
                )

                st.plotly_chart(fig, use_container_width="stretch")
                if annotation and annotation["exons"]:
                    st.caption(
                        f"Gene model from {annotation['path'].name} · {len(annotation['exons'])} exons · "
                        f"strand {annotation['strand']} · Exon numbers follow transcript orientation. "
                    )
                else:
                    st.caption(
                        "No matching per-gene GFF was found in the annotations folder. "
                        "The selected amplicon is shown as one assay; Fa/Fb and R identify the primer boundaries."
                    )

                st.markdown("### 🔍 Selected Amplicon Details")
                st.caption(
                    f"{selected_amp['marker']} · {selected_amp['amp_size']:,} bp amplicon · "
                    f"{selected_amp['forward'].replace('Forward Primer ', 'F-')} + Common Reverse"
                )

                detail_left, detail_right = st.columns([1, 1.35])

                with detail_left:
                    st.markdown("**Amplification Pattern**")
                    st.caption(
                        f"Target allele: **{selected_amp['allele']}** · "
                        f"Allele call/size: **{selected_amp['allele_call']}**"
                    )

                    if pd.notna(img_path) and str(img_path).strip() and os.path.exists(str(img_path).strip()):
                        st.image(
                            str(img_path).strip(),
                            caption=f"Assay pattern: {selected_amp['marker']}",
                            use_container_width="stretch",
                        )
                    elif pd.notna(img_path) and str(img_path).strip():
                        st.warning(f"Image path registered (`{img_path}`), but file was not found on disk.")
                    else:
                        st.info("No amplification image registered for this marker.")

                with detail_right:
                    st.markdown("**Amplicon Sequence**")
                    amp_start = selected_amp["amp_start"]
                    amp_end = selected_amp["amp_end"]
                    amplicon_seq = sequence[amp_start:amp_end]

                    st.code(
                        f">{selected_amp['marker']}_{selected_amp['amp_size']}bp\n"
                        + "\n".join(
                            amplicon_seq[i:i + 80]
                            for i in range(0, len(amplicon_seq), 80)
                        ),
                        language=None,
                    )

                    st.caption(
                        f"Reference coordinates: {amp_start + 1:,}–{amp_end:,} bp · "
                        f"{len(amplicon_seq):,} bp"
                    )

                    selected_primer_rows = result_df[result_df["Marker"] == selected_amp["marker"]].copy()
                    if not selected_primer_rows.empty:
                        st.markdown("**Primer mapping**")
                        st.dataframe(
                            selected_primer_rows[[
                                "Primer", "Orientation", "Start", "End", "Matches", "Status"
                            ]],
                            use_container_width="stretch",
                            hide_index=True,
                        )

            else:
                st.info(
                    "No complete amplicons could be constructed because the mapped primer pairs do not include "
                    "both a forward primer and a common reverse primer. Check the Mapping Data Table below."
                )

            tab_data = st.container()
            st.markdown("### 📋 Mapping Data Table")

            def _status_color(val):
                if val == "No match":
                    return f"color:{COLOR_FWD_B_TEXT};font-weight:600;"
                if val == "Exact match":
                    return f"color:{COLOR_REV_TEXT};font-weight:600;"
                if isinstance(val, str) and val.startswith("Multiple"):
                    return f"color:{COLOR_ACCENT_TEXT};font-weight:600;"
                return ""

            def _status_icon(val):
                if val == "No match":
                    return f"✗ {val}"
                if val == "Exact match":
                    return f"✓ {val}"
                if isinstance(val, str) and val.startswith("Multiple"):
                    return f"⚠ {val}"
                return val

            try:
                styled = result_df.style.map(_status_color, subset=["Status"])
            except AttributeError:
                styled = result_df.style.applymap(_status_color, subset=["Status"])
            styled = styled.format({"Status": _status_icon})

            st.dataframe(styled, use_container_width="stretch", hide_index=True, height=260)


# ============================================================
# 5. FASTA VIEWER
# ============================================================
elif page == "FASTA Viewer":
    st.title("FASTA Viewer")

    seq_df = run_query("SELECT * FROM sequences")

    if seq_df.empty:
        st.info("No reference sequences found.")
    elif "Genomic_sequence" not in seq_df.columns:
        st.error("The `sequences` table has no `Genomic_sequence` column.")
    else:
        genes = sorted(seq_df["target_gene"].dropna().unique().tolist())

        c1, c2 = st.columns([1, 2])
        with c1:
            gene_pick = st.selectbox(
                "Target Gene", ["All"] + genes,
                help="Filter reference sequences by resistance gene.",
            )
            filtered = seq_df if gene_pick == "All" else seq_df[seq_df["target_gene"] == gene_pick]

        def sequence_label(row):
            acc = row.get("accession_or_locus_tag", row.get("sequence_id", "Unknown"))
            return f"{row.get('target_gene', '')} · {row.get('Reference_genome', '')} · {acc} · {row.get('sense_strand', '')}"

        labels = {sequence_label(r): idx for idx, r in filtered.iterrows()}

        if labels:
            with c2:
                selected = st.selectbox("Sequence Accession", list(labels))
            row = filtered.loc[labels[selected]]

            raw = str(row["Genomic_sequence"]).upper().replace("\n", "").replace(" ", "")
            length = len(raw)
            gc = (raw.count("G") + raw.count("C")) / length * 100 if length else 0
            n_count = raw.count("N")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Reference", str(row.get("Reference_genome", "N/A")))
            c2.metric("Length", f"{length:,} bp")
            c3.metric("GC Content", f"{gc:.1f}%")
            c4.metric("N Bases", f"{n_count:,}")

            if n_count:
                st.caption(f"⚠️ Contains {n_count:,} ambiguous (N) base{'s' if n_count != 1 else ''}.")

            acc = row.get("accession_or_locus_tag", row.get("sequence_id", "seq"))
            gene = row.get("target_gene", "gene")
            strand = row.get("sense_strand", "")
            header = f">{acc}_{gene}_{strand}".replace(" ", "_")

            wrap_width = st.slider(
                "Line width", min_value=40, max_value=120, value=60, step=10,
                help="Characters per line in the FASTA record.",
            )
            wrapped = "\n".join(raw[i:i + wrap_width] for i in range(0, length, wrap_width))
            fasta = f"{header}\n{wrapped}"

            st.download_button(
                "Download FASTA File",
                fasta,
                f"{acc}_{gene}.fasta".replace(" ", "_"),
                "text/plain",
            )

            st.markdown("**FASTA Record** *(use the copy icon in the top-right corner)*")
            st.code(fasta, language=None)

            with st.expander("Sequence Metadata"):
                st.dataframe(row.drop(labels=["_label"], errors="ignore").to_frame().T,
                             use_container_width="stretch", hide_index=True)
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

    EXAMPLE_QUERIES = {
        "Markers for the I gene": default_sql,
        "Marker count per locus": (
            "SELECT target_gene, COUNT(*) AS marker_count\n"
            "FROM markers\n"
            "GROUP BY target_gene\n"
            "ORDER BY marker_count DESC"
        ),
        "All genes on a given chromosome": "SELECT * FROM genes WHERE chromosome LIKE '%2%'",
        "Sequences missing an accession": (
            "SELECT * FROM sequences\n"
            "WHERE accession_or_locus_tag IS NULL OR TRIM(accession_or_locus_tag) = ''"
        ),
    }

    if "sql_query_text" not in st.session_state:
        st.session_state.sql_query_text = default_sql

    def _load_example():
        st.session_state.sql_query_text = EXAMPLE_QUERIES[st.session_state.sql_example_pick]

    with st.expander("📖 Table schema reference", expanded=False):
        st.caption("Column names and types for each table — handy when writing a query below.")
        schema_tabs = st.tabs(["genes", "markers", "primers", "sequences"])
        for tab, table in zip(schema_tabs, ["genes", "markers", "primers", "sequences"]):
            with tab:
                schema_df = get_table_schema(table)
                if schema_df is not None and not schema_df.empty:
                    st.dataframe(schema_df, use_container_width="stretch", hide_index=True, height=180)
                else:
                    st.caption("Schema unavailable for this table.")

    c_ex1, c_ex2 = st.columns([3, 1])
    with c_ex1:
        st.selectbox(
            "Example queries", list(EXAMPLE_QUERIES),
            key="sql_example_pick", label_visibility="collapsed",
        )
    with c_ex2:
        st.button("Load example ➜", use_container_width="stretch", on_click=_load_example)

    query = st.text_area(
        "SQL Query (Read-Only)", key="sql_query_text", height=140,
        help="SELECT / WITH statements only — one statement per run.",
    )

    if st.button("Run Query", type="primary"):
        ok, msg = is_safe_select(query)
        if not ok:
            st.error(msg)
        else:
            try:
                t0 = time.perf_counter()
                with sqlite3.connect(f"file:{DB_NAME}?mode=ro", uri=True) as conn:
                    result = pd.read_sql_query(query, conn)
                elapsed_ms = (time.perf_counter() - t0) * 1000

                st.success(f"{len(result)} rows returned in {elapsed_ms:.0f} ms.")
                st.dataframe(result, use_container_width="stretch", hide_index=True, height=280)

                st.download_button(
                    "Export Results (CSV)",
                    result.to_csv(index=False).encode("utf-8"),
                    "query_results.csv",
                    "text/csv",
                )
            except Exception as e:
                st.error(f"SQL execution error: {e}")