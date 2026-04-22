#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(httr)
  library(jsonlite)
})

# =========================
# HPO utilities
# =========================
get_genes_from_hpo_codes <- function(hpo_codes) {
  genes_by_hpo <- list()

  for (hpo in strsplit(hpo_codes, ";")[[1]]) {
    encoded <- gsub(":", "%3A", hpo)
    url <- paste0("https://ontology.jax.org/api/network/annotation/", encoded)

    resp <- GET(url)
    data <- fromJSON(content(resp, "text"))

    if (!is.null(data$genes$name) && length(data$genes$name) < 1000) {
      genes_by_hpo[[hpo]] <- data$genes$name
    }
  }

  unique(unlist(genes_by_hpo))
}

# =========================
# Panel construction
# =========================
build_gene_panel <- function(panel_file = NULL,
                             hpo_codes = NULL,
                             offline = FALSE) {

  panel_genes <- character(0)
  print(panel_file)

  # 1. Static panel
  if (!is.null(panel_file)) {
    print("PANEL FILE IS NOT NULL!")
    panel_df <- read.csv(panel_file, header = TRUE, stringsAsFactors = FALSE)
    panel_genes <- panel_df[[1]]
    print("PANEL FILE GENES:")
    print(panel_genes)
  }

  # 2. HPO-derived genes
  if (!is.null(hpo_codes) && !offline) {
    print("CALLING HPO API!")
    hpo_genes <- get_genes_from_hpo_codes(hpo_codes)
    panel_genes <- c(panel_genes, hpo_genes)
    print("HPO PANEL GENES:")
    print(panel_genes)
  }

  unique(panel_genes)
}

# =========================
# Drop rows where all columns are NA
# =========================
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

  # Panel filter
  if (!is.null(panel_genes) && length(panel_genes) > 0 && "Hugo_Symbol" %in% colnames(filtered)) {
    keep <- !is.na(filtered$Hugo_Symbol) &
            filtered$Hugo_Symbol %in% panel_genes
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
  if (drop_benign && "CLIN_SIG" %in% colnames(filtered)) {
    keep <- !grepl("benign", filtered$CLIN_SIG, ignore.case = TRUE)
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
hpo_codes     <- normalize_arg(args[3])
offline       <- if (!is.null(args[4])) as.logical(args[4]) else FALSE
panel_file    <- normalize_arg(args[5])
max_freq      <- if (!is.null(normalize_arg(args[6]))) as.numeric(args[6]) else NULL
drop_benign   <- if (!is.null(normalize_arg(args[7]))) as.logical(args[7]) else FALSE

# =========================
# Load MAF
# =========================
raw_maf <- tryCatch(
  read.table(
    maf_file,
    sep = "\t",
    header = TRUE,
    quote = "",
    comment.char = "",
    fill = TRUE,
    stringsAsFactors = FALSE,
    check.names = FALSE
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
      check.names = FALSE
    )
  }
)

write.table(
  raw_maf,
  paste0(patient_code, ".raw.maf"),
  sep = "\t",
  quote = FALSE,
  row.names = FALSE
)

# =========================
# Build panel and filter
# =========================
panel_genes <- build_gene_panel(
  panel_file = panel_file,
  hpo_codes  = hpo_codes,
  offline    = offline
)

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
  row.names = FALSE
)
