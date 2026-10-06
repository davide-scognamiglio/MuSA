#!/usr/bin/env Rscript

# =========================
# Panel construction
# =========================
# The static panel (--panel) is a gene list. The phenotype panel is no longer looked up online:
# HPO_MATCH has already marked each row HPO_panel = yes/no from the patient's HPO terms and the
# installed HPO release (bin/hpo_match.py), and "." when no term is specific enough to filter on.
read_static_panel <- function(panel_file = NULL) {
  if (is.null(panel_file)) return(character(0))
  panel_df <- read.csv(panel_file, header = TRUE, stringsAsFactors = FALSE)
  genes <- unique(panel_df[[1]])
  message("Static panel: ", length(genes), " genes")
  genes
}

# =========================
# Drop rows where all columns are NA
# =========================
# Correctly catches a row that is all "." or all empty-string too, now that read.table's
# na.strings (below) folds every missing-value spelling into real NA before this ever runs —
# previously only an all-literal-"NA" row would trip is.na() here.
drop_all_na_rows <- function(df) {
  if (nrow(df) == 0) return(df)
  df[rowSums(is.na(df)) < ncol(df), , drop = FALSE]
}

# =========================
# Filtering logic
# =========================
filter_maf <- function(maf,
                       panel_genes = NULL,
                       max_freq = NULL,
                       drop_benign = FALSE) {

  filtered <- maf

  # Panel filter: a row stays if its gene is in the static panel or HPO_MATCH put it in the
  # phenotype panel. Either panel on its own filters; with neither, nothing is dropped here.
  use_static <- length(panel_genes) > 0 && "Hugo_Symbol" %in% colnames(filtered)
  use_hpo    <- "HPO_panel" %in% colnames(filtered) && any(!is.na(filtered$HPO_panel))
  if (use_static || use_hpo) {
    keep <- rep(FALSE, nrow(filtered))
    if (use_static) keep <- keep | (!is.na(filtered$Hugo_Symbol) & filtered$Hugo_Symbol %in% panel_genes)
    if (use_hpo)    keep <- keep | (!is.na(filtered$HPO_panel) & filtered$HPO_panel == "yes")
    message("Panel filter (", paste(c(if (use_static) "static", if (use_hpo) "HPO"), collapse = " + "),
            "): ", sum(keep), " of ", nrow(filtered), " variants kept")
    filtered <- filtered[keep, , drop = FALSE]
  }

  # Frequency filter
  if (!is.null(max_freq) && "MAX_AF" %in% colnames(filtered)) {
    af <- suppressWarnings(as.numeric(filtered$MAX_AF))
    keep <- is.na(af) | af < max_freq
    keep[is.na(keep)] <- FALSE
    filtered <- filtered[keep, , drop = FALSE]
  }

  # Drop benign variants
  if (drop_benign && "encoded_CLNSIG" %in% colnames(filtered)) {
    keep <- !grepl("benign", filtered$encoded_CLNSIG, ignore.case = TRUE)
    keep[is.na(keep)] <- TRUE
    filtered <- filtered[keep, , drop = FALSE]
  }

  filtered
}

# =========================
# Argument parsing
# =========================
args <- commandArgs(trailingOnly = TRUE)

normalize_arg <- function(x) {
  if (is.null(x) || length(x) == 0 || x %in% c("null", "NULL", "")) {
    NULL
  } else {
    x
  }
}

maf_file      <- normalize_arg(args[1])
patient_code  <- normalize_arg(args[2])
# args[3] (HPO terms) and args[4] (offline) are no longer read: HPO_MATCH turns the terms into the
# HPO_panel column upstream, with no network. Kept as positions so the module call is unchanged.
panel_file    <- normalize_arg(args[5])
max_freq      <- if (!is.null(normalize_arg(args[6]))) as.numeric(args[6]) else NULL
drop_benign   <- if (!is.null(normalize_arg(args[7]))) as.logical(args[7]) else FALSE

# =========================
# Load MAF
# =========================
# na.strings covers every missing-value spelling the upstream tools + MERGE_ANNOTATIONS's outer
# join produce for a whole cell ("NA" from the join's `-e "NA"` fill, "" from VEP fields
# with no match, "." from dbNSFP's own convention) — R's na.strings is a whole-cell match, so a
# multi-transcript array like ".;.;.;0.901;.;." is untouched; only a cell that IS exactly one of
# these three strings becomes NA. Paired with `na = "."` on both write.table calls below, every
# flavor of missing collapses to the single "." spelling in the published MAF.
NA_SPELLINGS <- c("NA", "", ".")

raw_maf <- tryCatch(
  read.table(
    maf_file,
    sep = "\t",
    header = TRUE,
    quote = "",
    comment.char = "",
    fill = TRUE,
    stringsAsFactors = FALSE,
    check.names = FALSE,
    na.strings = NA_SPELLINGS
  ),
  error = function(e) {
    message("Warning: malformed lines detected — retrying with relaxed parsing.")
    read.table(
      maf_file,
      sep = "\t",
      header = TRUE,
      quote = "",
      comment.char = "",
      fill = TRUE,
      stringsAsFactors = FALSE,
      check.names = FALSE,
      na.strings = NA_SPELLINGS
    )
  }
)

write.table(
  raw_maf,
  paste0(patient_code, ".raw.maf"),
  sep = "\t",
  quote = FALSE,
  row.names = FALSE,
  na = "."
)

# =========================
# Build panel and filter
# =========================
panel_genes <- read_static_panel(panel_file)

filtered_maf <- filter_maf(
  maf         = raw_maf,
  panel_genes = panel_genes,
  max_freq    = max_freq,
  drop_benign = drop_benign
)

filtered_maf <- drop_all_na_rows(filtered_maf)

write.table(
  filtered_maf,
  paste0(patient_code, ".filtered.maf"),
  sep = "\t",
  quote = FALSE,
  row.names = FALSE,
  na = "."
)
