#!/usr/bin/env Rscript

# ==============================================================================
# MAF Dashboard Generator - Refactored
# ==============================================================================

# ---- Configuration ----
COLUMN_CONFIG <- list(
  main = list(
    online = c(
      "SYMBOL",
      "HGVSc",
      "genome_change",
      "HGVSp_Short",
      "Variant_Classification",
      "CLIN_SIG",
      "acmg_score",
      "acmg_criteria",
      "MAX_AF",
      "MAX_AF_POPS",
      "PL_score",
      "PUBMED",
      "Franklin"
    ),
    offline = c(
      "SYMBOL",
      "HGVSc",
      "genome_change",
      "HGVSp_Short",
      "Variant_Classification",
      "CLIN_SIG",
      "MAX_AF",
      "MAX_AF_POPS",
      "PL_score",
      "PUBMED",
      "Franklin"
    )
  ),
  
  details = list(
    with_plugins = c("clinvar_OMIM_id", "clinvar_review", "clinvar_trait",
                     "PhenotypeOrthologous_Mouse_phenotype",
                     "PhenotypeOrthologous_Rat_phenotype"),
    without_plugins = c("")
  ),
  
  # Display names mapping (internal_name -> display_name)
  display_names = c(
    "Hugo_Symbol" = "gene",
    "genome_change" = "gDNA",
    "HGVSp_Short" = "a.a.",
    "Variant_Classification" = "type",
    "CLIN_SIG" = "clinvar",
    "acmg_score" = "suggested classification",
    "acmg_criteria" = "acmg criteria",
    "MAX_AF" = "max AF",
    "MAX_AF_POPS" = "max AF pop",
    "PL_score" = "Renovo score",
    "PUBMED" = "PUBMED",
    "HGVSc" = "cDNA",
    "Franklin" = "Franklin",
    "clinvar_OMIM_id" = "OMIM",
    "clinvar_review" = "clinvar review",
    "clinvar_trait" = "clinvar trait",
    "PhenotypeOrthologous_Mouse_phenotype" = "Mouse phenotype",
    "PhenotypeOrthologous_Rat_phenotype" = "Rat phenotype"
  )
)

CUSTOM_CSS <- "
  * { margin: 0; padding: 0; box-sizing: border-box; }
  
  body { 
    background: linear-gradient(135deg, #209957 0%, #764ba2 100%);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    padding: 40px 20px;
    min-height: 100vh;
  }
  
  .container { 
    max-width: 1600px; 
    margin: auto;
  }
  
  .header-section {
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    border-radius: 20px;
    padding: 40px;
    margin-bottom: 30px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.3);
  }
  
  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 30px;
    flex-wrap: wrap;
  }
  
  .header-left h1 { 
    color: #1a202c;
    font-weight: 800; 
    font-size: 42px;
    margin-bottom: 8px;
    background: linear-gradient(135deg, #209957 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  
  .patient-id {
    display: inline-block;
    background: linear-gradient(135deg, #209957 0%, #764ba2 100%);
    color: white;
    padding: 6px 16px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 35px;
    margin-bottom: 12px;
  }
  
  .meta-info {
    display: flex;
    gap: 24px;
    margin-top: 12px;
    flex-wrap: wrap;
  }
  
  .meta-item {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #4a5568;
    font-size: 20px;
  }
  
  .meta-item-icon {
    width: 18px;
    height: 18px;
    color: #209957;
  }
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
  }
  
  .stat-card {
    background: linear-gradient(135deg, #209957 0%, #764ba2 100%);
    border-radius: 12px;
    padding: 20px;
    color: white;
    text-align: center;
  }
  
  .stat-value {
    font-size: 32px;
    font-weight: 800;
    margin-bottom: 4px;
  }
  
  .stat-label {
    font-size: 13px;
    opacity: 0.9;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  
  .card { 
    border-radius: 20px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.1);
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    padding: 32px;
    margin-bottom: 24px;
    border: 1px solid rgba(255, 255, 255, 0.3);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
  }
  
  .card:hover {
    transform: translateY(-4px);
    box-shadow: 0 30px 80px rgba(0, 0, 0, 0.15);
  }
  
  .card-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 2px solid #e2e8f0;
  }
  
  .card-icon {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, #209957 0%, #764ba2 100%);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 700;
    font-size: 18px;
  }
  
  .card-title { 
    font-weight: 700;
    color: #1a202c;
    font-size: 24px;
    margin: 0;
  }
  
  .plot-container {
    background: #f7fafc;
    border-radius: 12px;
    padding: 16px;
    border: 1px solid #e2e8f0;
  }
  
  .plot-container img {
    max-width: 100%;
    height: auto;
    border-radius: 8px;
    display: block;
  }
  
  .grid-2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
    gap: 24px;
  }
  
  footer {
    margin-top: 40px;
    padding: 24px;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    border-radius: 20px;
    text-align: center;
    color: #4a5568;
    font-size: 14px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.3);
  }
  
  footer strong {
    color: #209957;
    font-weight: 600;
  }
  
  .pipeline-badge {
    display: inline-block;
    background: #f7fafc;
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 13px;
    color: #4a5568;
    margin-top: 8px;
  }
  
  /* Reactable customization */
  .reactable {
    font-size: 14px;
  }
  
  @media (max-width: 768px) {
    .header-content {
      flex-direction: column;
      align-items: flex-start;
    }
    
    .grid-2 {
      grid-template-columns: 1fr;
    }
    
    .header-left h1 {
      font-size: 32px;
    }
  }
"

# ---- Libraries ----
suppressPackageStartupMessages({
  library(maftools)
  library(readr)
  library(dplyr)
  library(reactable)
  library(htmltools)
  library(htmlwidgets)
  library(base64enc)
  library(ggplot2)
  library(gridExtra)
  library(cowplot)
})

# ==============================================================================
# Utility Functions
# ==============================================================================

#' Parse command line arguments
parse_args <- function(args) {
  if (length(args) < 5) {
    stop("Usage: Rscript html_reporter.R patient_code workflow use_vep_plugins offline skip_genebe")
  }
  
  list(
    patient_code = args[1],
    workflow = args[2],
    use_vep_plugins = as.logical(toupper(args[3]) == "TRUE"),
    offline = as.logical(toupper(args[4]) == "TRUE"),
    skip_genebe = as.logical(toupper(args[5]) == "TRUE")
  )
}

#' Generate Franklin URL from genome change notation
make_franklin_url <- function(genome_change) {
  if (is.na(genome_change) || genome_change == "") return(NA_character_)
  
  gc <- sub("^g\\.", "", genome_change)
  chr <- sub("^chr([^:]+):.*", "\\1", gc)
  
  # SNV pattern
  if (grepl("[ACGT]>[ACGT]$", gc)) {
    pos <- sub("^chr[^:]+:([0-9]+).*", "\\1", gc)
    ref <- sub(".*([ACGT])>[ACGT]$", "\\1", gc)
    alt <- substr(genome_change, nchar(genome_change), nchar(genome_change))
    
    # Insertion pattern
  } else if (grepl("ins", gc)) {
    pos <- sub("^chr[^:]+:([0-9]+)_.*", "\\1", gc)
    ins <- sub(".*ins", "", gc)
    ref <- sub(".*:([ACGT])_.*", "\\1", gc)
    alt <- paste0(ref, ins)
    
    # Deletion pattern
  } else if (grepl("del", gc)) {
    pos <- sub("^chr[^:]+:([0-9]+)_.*", "\\1", gc)
    delseq <- sub(".*del", "", gc)
    ref <- delseq
    alt <- substr(delseq, 1, 1)
    
  } else {
    return(NA_character_)
  }
  
  sprintf(
    "https://franklin.genoox.com/clinical-db/variant/snp/chr%s-%s-%s-%s-hg38",
    chr, pos, ref, alt
  )
}

#' Convert PNG file to data URI
img_to_datauri <- function(path) {
  if (!file.exists(path)) return(NULL)
  b <- base64enc::base64encode(path)
  paste0("data:image/png;base64,", b)
}

# ==============================================================================
# MAF Reading and Processing
# ==============================================================================

#' Safely read MAF file
read_maf_safe <- function(path) {
  if (!file.exists(path)) return(NULL)
  
  df <- tryCatch(
    read.table(
      path,
      sep = '\t',
      header = TRUE,
      quote = '',
      comment.char = '',
      fill = TRUE,
      stringsAsFactors = FALSE,
      check.names = FALSE
    ),
    error = function(e) NULL
  )
  
  if (is.null(df)) return(NULL)
  if (nrow(df) == 0) return("HEADER_ONLY")
  
  df
}

#' Load MAF with fallback logic
load_maf_data <- function(patient_code) {
  filtered_maf <- paste0(patient_code, ".filtered.maf")
  raw_maf <- paste0(patient_code, ".raw.maf")
  
  maf_df <- read_maf_safe(filtered_maf)
  
  if (identical(maf_df, "HEADER_ONLY")) {
    message("Filtered MAF contains only header, falling back to raw MAF")
    maf_df <- read_maf_safe(raw_maf)
  }
  
  if (is.null(maf_df)) {
    stop("Neither filtered nor raw MAF could be read for patient: ", patient_code)
  }
  
  if (identical(maf_df, "HEADER_ONLY")) {
    stop("Both filtered and raw MAF contain only headers for patient: ", patient_code)
  }
  
  # Remove duplicate columns
  maf_df[, !duplicated(colnames(maf_df))]
}

#' Create maftools object from dataframe
create_maf_object <- function(maf_df) {
  required_cols <- c(
    "Hugo_Symbol", "Chromosome", "Start_Position", 
    "End_Position", "Reference_Allele", "Tumor_Seq_Allele2"
  )
  
  missing_cols <- setdiff(required_cols, colnames(maf_df))
  if (length(missing_cols) > 0) {
    stop("Missing required MAF columns: ", paste(missing_cols, collapse = ", "))
  }
  
  var_types <- unique(maf_df$Variant_Classification)
  
  tryCatch({
    read.maf(maf = maf_df, vc_nonSyn = var_types, verbose = TRUE)
  }, error = function(e) {
    message("⚠️  read.maf() failed: ", conditionMessage(e))
    stop("Failed to create maf object. Check column names and contents.")
  })
}

# ==============================================================================
# Visualization Functions
# ==============================================================================

#' Generate all MAF plots and return as data URIs
generate_maf_plots <- function(maf_obj, patient_code, workflow) {
  tmpdir <- tempdir()
  plots <- list()
  
  # Summary plot
  png_summary <- file.path(tmpdir, paste0(patient_code, "_maf_summary.png"))
  png(filename = png_summary, width = 1400, height = 800, res = 150)
  try(plotmafSummary(maf = maf_obj, rmOutlier = TRUE, addStat = 'median', dashboard = TRUE), silent = TRUE)
  dev.off()
  plots$summary <- img_to_datauri(png_summary)
  
  # Skip tumor-specific plots for germline workflow
  if (workflow == "annotate") {
    return(plots)
  }
  
  # Oncoplot
  png_oncoplot <- file.path(tmpdir, paste0(patient_code, "_oncoplot.png"))
  png(filename = png_oncoplot, width = 1200, height = 800, res = 150)
  try(oncoplot(maf = maf_obj, top = 20), silent = TRUE)
  dev.off()
  plots$oncoplot <- img_to_datauri(png_oncoplot)
  
  # Lollipop plot for top gene
  top_genes <- getGeneSummary(maf_obj)
  if (nrow(top_genes) > 0) {
    plots$top_gene <- top_genes$Hugo_Symbol[1]
    png_lollipop <- file.path(tmpdir, paste0(patient_code, "_lollipop.png"))
    png(filename = png_lollipop, width = 1000, height = 600, res = 150)
    try(lollipopPlot(maf = maf_obj, gene = plots$top_gene), silent = TRUE)
    dev.off()
    plots$lollipop <- img_to_datauri(png_lollipop)
  }
  
  # Tumor mutation burden
  png_tmb <- file.path(tmpdir, paste0(patient_code, "_tmb.png"))
  png(filename = png_tmb, width = 1000, height = 600, res = 150)
  try({
    tmb_res <- tmb(maf = maf_obj)
    barplot(tmb_res$tmb, names.arg = tmb_res$Tumor_Sample_Barcode, 
            las = 2, cex.names = 0.6, main = "Tumor Mutation Burden")
  }, silent = TRUE)
  dev.off()
  plots$tmb <- img_to_datauri(png_tmb)
  
  plots
}

# ==============================================================================
# Data Preparation Functions
# ==============================================================================

#' Select columns based on configuration
select_columns <- function(maf_df, config, offline, use_vep_plugins) {
  # Determine main columns
  main_cols <- if (offline) {
    config$main$offline
  } else {
    config$main$online
  }
  
  # Determine details columns
  details_cols <- if (use_vep_plugins) {
    config$details$with_plugins
  } else {
    config$details$without_plugins
  }
  
  # Keep only existing columns
  main_cols <- intersect(main_cols, colnames(maf_df))
  details_cols <- intersect(details_cols, colnames(maf_df))
  
  list(
    main = main_cols,
    details = details_cols,
    all = c(main_cols, details_cols)
  )
}

#' Apply display names to columns
apply_display_names <- function(df, selected_cols, display_map) {
  # Get display names for main columns
  main_display <- sapply(selected_cols$main, function(col) {
    if (col %in% names(display_map)) display_map[[col]] else col
  })
  
  # Get display names for details columns (just replace underscores)
  details_display <- gsub("_", " ", selected_cols$details)
  
  # Subset and rename
  df_subset <- df[, selected_cols$all, drop = FALSE]
  colnames(df_subset) <- c(main_display, details_display)
  
  list(
    df = df_subset,
    main_display = main_display,
    details_display = details_display
  )
}

#' Format PUBMED IDs as clickable links
format_pubmed_links <- function(df) {
  if (!"PUBMED" %in% colnames(df)) return(df)
  
  df$PUBMED <- sapply(df$PUBMED, function(x) {
    if (is.na(x) || x == "") return("")
    
    ids <- trimws(unlist(strsplit(as.character(x), ",")))
    links <- sprintf(
      '<a href="https://pubmed.ncbi.nlm.nih.gov/%s/" target="_blank">%s</a>',
      ids, ids
    )
    htmltools::HTML(paste(links, collapse = ", "))
  })
  
  df
}

#' Add Franklin links column
add_franklin_links <- function(df) {
  if (!"gDNA" %in% colnames(df)) return(df)
  
  df$Franklin <- vapply(df$`gDNA`, make_franklin_url, character(1))
  df
}

format_phenotype <- function(value) {
  if (is.na(value) || value == "") return("")
  
  # Split by comma
  items <- unlist(strsplit(value, ","))
  # Replace underscores with spaces
  items <- gsub("_", " ", items)
  # Join with <br> for line breaks in HTML
  paste(unique(items), collapse = ", ")
}

#' Prepare final dataframe for display
prepare_display_data <- function(maf_df, config, offline, use_vep_plugins) {
  maf_df <- maf_df %>%
    mutate(across(everything(), ~ ifelse(is.na(.x), '', as.character(.x))))
  
  selected_cols <- select_columns(maf_df, config, offline, use_vep_plugins)
  display_data <- apply_display_names(maf_df, selected_cols, config$display_names)
  
  df <- display_data$df
  df <- format_pubmed_links(df)
  df <- add_franklin_links(df)
  # Adjust the suggested classification column
  df <- adjust_suggested_classification(df)
  # Only prettify the phenotype columns
  phenotype_cols <- c(
    "PhenotypeOrthologous Mouse phenotype",
    "PhenotypeOrthologous Rat phenotype"
  )
  
  for (col in phenotype_cols) {
    if (col %in% colnames(df)) {
      df[[col]] <- vapply(df[[col]], format_phenotype, character(1))
    }
  }
  
  if ("acmg score" %in% colnames(df)) {
    df$`acmg score` <- as.numeric(df$`acmg score`)
  }
  
  list(
    df = df,
    main_cols = unique(c(display_data$main_display, if ("Franklin" %in% colnames(df)) "Franklin")),
    details_cols = gsub("_", " ", intersect(selected_cols$details, colnames(maf_df)))  # map to df columns
  )
}



# ==============================================================================
# Reactable Table Functions
# ==============================================================================

#' Create custom column definitions
create_column_defs <- function() {
  list(
    `max AF` = colDef(
      cell = function(value) {
        if (is.na(value) || value == "") {
          "Private"
        } else if (as.numeric(value) > 0.05) {
          sprintf("Common (%s)", value)
        } else {
          sprintf("Rare (%s)", value)
        }
      }
    ),
    
    `suggested classification` = colDef(
      cell = function(value) {
        if (is.na(value) || value == "") return("VUS")
        
        val <- as.numeric(value)
        if (val <= -7) sprintf("Benign (%s)", value)
        else if (val <= -1) sprintf("Likely benign (%s)", value)
        else if (val <= 5) sprintf("VUS (%s)", value)
        else if (val <= 9) sprintf("Likely Pathogenic (%s)", value)
        else sprintf("Pathogenic (%s)", value)
      }
    ),
    
    Franklin = colDef(
      html = TRUE,
      minWidth = 120,
      cell = function(value) {
        if (is.na(value)) "" else sprintf(
          '<a href="%s" target="_blank" rel="noopener noreferrer" style="color: #209957; font-weight: 600; text-decoration: none;">🔗 Franklin</a>',
          value
        )
      }
    ),
    
    PUBMED = colDef(html = TRUE,width = 100,align = "center"),
    `PhenotypeOrthologous Mouse phenotype` = colDef(
      html = TRUE,
      cell = function(value) format_phenotype(value),
      minWidth = 200
    ),
    
    `PhenotypeOrthologous Rat phenotype` = colDef(
      html = TRUE,
      cell = function(value) format_phenotype(value),
      minWidth = 200
    )
  )
}


# ==============================================================================
# Suggested Classification Adjustment
# ==============================================================================

adjust_suggested_classification <- function(df) {
  # Ensure the relevant columns exist
  required_cols <- c("type", "Renovo score", "suggested classification")
  missing_cols <- setdiff(required_cols, colnames(df))
  if (length(missing_cols) > 0) {
    warning("Missing columns for adjustment: ", paste(missing_cols, collapse = ", "))
    return(df)
  }
  
  df$`suggested classification` <- as.numeric(df$`suggested classification`)
  df$`Renovo score` <- as.numeric(df$`Renovo score`)
  
  # Define the adjustment function
  df <- df %>%
    rowwise() %>%
    mutate(
      `suggested classification` = if (
        # ! type %in% c("In_Frame_Ins","In_Frame_Del",
        #               "Frame_Shift_Del","Frame_Shift_Ins") &&
        type == "Missense_Mutation" &&
        !is.na(`suggested classification`) &&
        `suggested classification` >= 0 &&
        `suggested classification` <= 5 &&
        !is.na(`Renovo score`)
      ) {
        if (`Renovo score` > 0.5) {
          # Push above 5
          5 + (`Renovo score` - 0.5) * 10  # Renovo=1 → 10
        } else {
          # Push below 0
          0 - (0.5 - `Renovo score`) * 10  # Renovo=0 → -5
        }
      } else {
        `suggested classification`
      }
    ) %>%
    ungroup()
  
  
  df
}



#' Build interactive reactable
build_reactable <- function(display_data) {
  df <- display_data$df
  main_cols <- display_data$main_cols
  details_cols <- display_data$details_cols
  
  reactable(
    df[, main_cols, drop = FALSE],
    
    defaultSorted = if("suggested classification" %in% main_cols) list(`suggested classification` = "desc") else list(`Renovo score` = "desc"),
    columns = create_column_defs(),
    
    searchable = TRUE,
    filterable = TRUE,
    pagination = TRUE,
    defaultPageSize = 10,
    highlight = TRUE,
    striped = TRUE,
    bordered = TRUE,
    compact = TRUE,
    
    defaultColDef = colDef(
      headerStyle = list(background = "#209957", color = "white", fontWeight = "600"),
      style = list(padding = "6px")
    ),
    
    details = if (length(details_cols) > 0 && details_cols[1] != "") {
      function(index) {
        row <- df[index, details_cols, drop = FALSE]
        reactable(
          row,
          searchable = FALSE,
          filterable = FALSE,
          pagination = FALSE,
          highlight = FALSE,
          striped = FALSE,
          bordered = TRUE,
          compact = TRUE,
          fullWidth = TRUE,
          defaultColDef = colDef(
            minWidth = 120,
            headerStyle = list(background = "#e5e7eb", fontWeight = "600"),
            style = list(padding = "4px")
          )
        )
      }
    } else NULL
  )
}

# ==============================================================================
# HTML Generation Functions
# ==============================================================================

#' Build HTML page
build_html_page <- function(patient_code, workflow, table, plots, maf_obj) {
  # Get summary statistics
  gene_summary <- getGeneSummary(maf_obj)
  variant_summary <- getSampleSummary(maf_obj)
  total_variants <- nrow(maf_obj@data)
  total_genes <- nrow(gene_summary)
  total_samples <- nrow(variant_summary)
  
  tags$html(
    lang = "en",
    tags$head(
      tags$title(sprintf('Variant Analysis Report: %s', patient_code)),
      tags$link(rel = "stylesheet", 
                href = "https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"),
      tags$style(HTML(CUSTOM_CSS)),
      tags$meta(charset = "utf-8"),
      tags$meta(name = "viewport", content = "width=device-width, initial-scale=1.0")
    ),
    tags$body(
      tags$div(
        class = "container",
        
        # Header Section
        tags$div(
          class = "header-section",
          tags$div(
            class = "header-content",
            tags$div(
              class = "header-left",
              tags$div(class = "patient-id", sprintf("Patient ID: %s", patient_code)),
              tags$h1("Genomic Variant Analysis Report"),
              tags$div(
                class = "meta-info",
                tags$div(
                  class = "meta-item",
                  tags$span("📅"),
                  tags$span(format(Sys.time(), "%B %d, %Y at %H:%M"))
                ),
                tags$div(
                  class = "meta-item",
                  tags$span("🔬"),
                  tags$span(sprintf("Workflow: %s", tools::toTitleCase(workflow)))
                ),
                tags$div(
                  class = "meta-item",
                  tags$span("🧬"),
                  tags$span("Reference: hg38")
                )
              )
            ),
            tags$div(
              class = "stats-grid",
              tags$div(
                class = "stat-card",
                tags$div(class = "stat-value", format(total_variants, big.mark = ",")),
                tags$div(class = "stat-label", "Total Variants")
              ),
              tags$div(
                class = "stat-card",
                tags$div(class = "stat-value", format(total_genes, big.mark = ",")),
                tags$div(class = "stat-label", "Affected Genes")
              ),
              tags$div(
                class = "stat-card",
                tags$div(class = "stat-value", total_samples),
                tags$div(class = "stat-label", "Samples")
              )
            )
          )
        ),
        
        # Interactive table
        tags$div(
          class = "card",
          tags$div(
            class = "card-header",
            tags$div(class = "card-icon", "📊"),
            tags$h2(class = "card-title", "Interactive Variant Browser")
          ),
          tags$div(style = "overflow:auto;", table)
        ),
        
        # Summary plot
        if (!is.null(plots$summary)) {
          tags$div(
            class = "card",
            tags$div(
              class = "card-header",
              tags$div(class = "card-icon", "📈"),
              tags$h2(class = "card-title", "Variant Summary Dashboard")
            ),
            tags$div(
              class = "plot-container",
              tags$img(src = plots$summary)
            )
          )
        },
        
        # Tumor-specific plots
        if (workflow != "germline" && !is.null(plots$oncoplot)) {
          list(
            tags$div(
              class = "card",
              tags$div(
                class = "card-header",
                tags$div(class = "card-icon", "🎯"),
                tags$h2(class = "card-title", "Mutation Landscape")
              ),
              tags$div(
                class = "grid-2",
                tags$div(
                  tags$h3(style = "font-size: 18px; font-weight: 600; color: #2d3748; margin-bottom: 12px;", 
                          "Top 20 Mutated Genes"),
                  tags$div(class = "plot-container", tags$img(src = plots$oncoplot))
                ),
                if (!is.null(plots$lollipop)) {
                  tags$div(
                    tags$h3(style = "font-size: 18px; font-weight: 600; color: #2d3748; margin-bottom: 12px;", 
                            sprintf("Protein Domains: %s", plots$top_gene)),
                    tags$div(class = "plot-container", tags$img(src = plots$lollipop))
                  )
                }
              )
            ),
            
            if (!is.null(plots$tmb)) {
              tags$div(
                class = "card",
                tags$div(
                  class = "card-header",
                  tags$div(class = "card-icon", "📊"),
                  tags$h2(class = "card-title", "Tumor Mutation Burden Analysis")
                ),
                tags$div(class = "plot-container", tags$img(src = plots$tmb))
              )
            }
          )
        },
        
        # Footer
        tags$footer(
          tags$div(
            HTML(sprintf(
              "Generated by <strong>MuSA</strong> pipeline<br>
              Patient: <strong>%s</strong> | Analysis Date: %s",
              patient_code,
              format(Sys.time(), "%Y-%m-%d")
            ))
          ),
          tags$div(
            class = "pipeline-badge",
            tags$a(
              href = "https://www.ior.it/curarsi-al-rizzoli/dr-scognamiglio-davide",  
              target = "_blank",             # opens in a new tab
              rel = "noopener noreferrer",   # security best practice
              "Developed by Davide Scognamiglio @IRCCS Istituto Ortopedico Rizzoli"
            )
          )
        )
      )
    )
  )
}

# ==============================================================================
# Main Pipeline
# ==============================================================================

main <- function(args) {
  # Parse arguments
  params <- parse_args(args)
  
  message("Loading MAF data...")
  maf_df <- load_maf_data(params$patient_code)
  
  message("Creating MAF object...")
  maf_obj <- create_maf_object(maf_df)
  
  message("Generating plots...")
  plots <- generate_maf_plots(maf_obj, params$patient_code, params$workflow)
  
  message("Preparing data for display...")
  display_data <- prepare_display_data(
    maf_df, 
    COLUMN_CONFIG, 
    params$offline || params$skip_genebe,
    params$use_vep_plugins
  )
  
  message("Building interactive table...")
  table <- build_reactable(display_data)
  
  message("Generating HTML page...")
  html_page <- build_html_page(params$patient_code, params$workflow, table, plots, maf_obj)
  
  # Save output
  outfile <- sprintf("%s_maf_dashboard.html", params$patient_code)
  htmltools::save_html(html_page, file = outfile, background = "#ffffff")
  
  cat("✓ Saved dashboard to:", outfile, "\n")
}

# ==============================================================================
# Script Entry Point
# ==============================================================================

if (!interactive()) {
  args <- commandArgs(trailingOnly = TRUE)
  main(args)
}