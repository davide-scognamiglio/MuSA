# -------------------- Load Libraries --------------------------
library(dplyr)
library(readr)
library(stringr)
library(parallel)

# -------------------- Read MAF -------------------------------
# this is a dummy maf file path
# it should be replaced by something like:
## Get command line arguments
# args <- commandArgs(trailingOnly = TRUE)
# 
# # Ensure three arguments are provided
# if (length(args) < 5) {
#   stop("Error: Please provide three arguments: <maf_path> <patientHPOs>")
# } 
# maf_path <- args[1]

maf_path <- "path/to/file.maf"

annotated_file <- read_delim(
  maf_path,
  delim = "\t",
  escape_double = FALSE,
  trim_ws = TRUE,
  guess_max = 100000,
  comment = "#"
)

# ------------------ Define ACMG Criteria ---------------------
acmg_criteria <- c(
  "PVS1",
  "PS1", "PS2", "PS3", "PS4",
  "PM1", "PM2", "PM3", "PM4", "PM5", "PM6",
  "PP1", "PP2", "PP3", "PP4", "PP5",
  "BA1",
  "BS1", "BS2", "BS3", "BS4",
  "BP1", "BP2", "BP3", "BP4", "BP5", "BP6", "BP7","BP8"
)

# Add ACMG columns filled with NA
for (crit in acmg_criteria) {
  annotated_file[[crit]] <- NA
}
annotated_file$suggested_classification <- NA
# ------------------ Identify Frequency and Prediction Columns -------------------

freq_keywords <- c("gnomad", "esp", "1000g", "1000_genomes", "exac", "topmed", "freq")
comp_keywords <- c("score")

colnames_lower <- tolower(colnames(annotated_file))

freq_cols <- colnames(annotated_file)[
  sapply(colnames_lower, function(x) any(str_detect(x, freq_keywords)))
]

comp_cols <- colnames(annotated_file)[
  sapply(colnames_lower, function(x) any(str_detect(x, comp_keywords)))
]

cat("Detected frequency columns:\n")
print(freq_cols)

cat("Detected computational prediction columns:\n")
print(comp_cols)


# ------------------ Helper Function: check_frequencies ------------------------

check_frequencies <- function(row, freq_cols) {
  freq_values <- c()
  
  for (fc in freq_cols) {
    val <- row[[fc]]
    val_num <- suppressWarnings(as.numeric(val))
    if (!is.na(val_num)) {
      freq_values <- c(freq_values, val_num)
    }
  }
  
  # PM2
  PM2 <- if (length(freq_values) == 0) {
    1
  } else if (any(freq_values < 0.01, na.rm = TRUE)) {
    1
  } else {
    NA
  }
  
  # BA1
  BA1 <- if (length(freq_values) > 0 && any(freq_values > 0.05, na.rm = TRUE)) {
    1
  } else {
    NA
  }
  
  # BS1
  BS1 <- if (length(freq_values) > 0 && any(freq_values > 0.01, na.rm = TRUE)) {
    1
  } else {
    NA
  }
  
  return(list(PM2 = PM2, BA1 = BA1, BS1 = BS1))
}


# ------------------ Helper Function: check_pred_tools ------------------------

check_pred_tools <- function(row, comp_cols) {
  pathogenic_terms <- c(
    "deleterious",
    "damaging",
    "probably damaging",
    "possibly damaging",
    "disease causing",
    "pathogenic"
  )
  
  pathogenic_hits <- 0
  
  for (cc in comp_cols) {
    val <- row[[cc]]
    val_low <- tolower(as.character(val))
    
    if (!is.na(val_low)) {
      if (any(str_detect(val_low, pathogenic_terms))) {
        pathogenic_hits <- pathogenic_hits + 1
      }
    }
  }
  
  PP3 <- if (pathogenic_hits > 0) {
    1
  } else {
    NA
  }
  
  return(PP3)
}


# ------------------ Helper Function: check_PVS1 ------------------------

check_PVS1 <- function(row) {
  # Define null variant classes relevant for PVS1
  null_classes <- c(
    "Nonsense_Mutation",
    "Frame_Shift_Del",
    "Frame_Shift_Ins",
    "Splice_Site",
    "Translation_Start_Site",
    "Nonstop_Mutation",
    "START_CODON_SNP"
  )
  
  var_class <- as.character(row[["Variant_Classification"]])
  lof_mechanism <- as.character(row[["ACMGLMMLof_LOF_Mechanism"]])
  
  # Check conditions
  if (!is.na(var_class) && 
      var_class %in% null_classes &&
      !is.na(lof_mechanism) &&
      lof_mechanism == "YES") {
    return(1)
  } else {
    return(NA)
  }
}

# ------------------ Main Function: check_acmg ------------------------

check_acmg <- function(df, freq_cols, comp_cols) {
  df <- df %>%
    rowwise() %>%
    mutate(
      # frequency checks
      freq_res = list(check_frequencies(cur_data(), freq_cols)),
      PM2 = freq_res$PM2,
      BA1 = freq_res$BA1,
      BS1 = freq_res$BS1,
      
      # computational predictions
      PP3 = check_pred_tools(cur_data(), comp_cols),
      
      # PVS1 check
      PVS1 = check_PVS1(cur_data()),
      
      # assign suggested_classification if BA1 is flagged
      suggested_classification = ifelse(!is.na(BA1) & BA1 == 1, "benign", NA)
    ) %>%
    select(-freq_res) %>%
    ungroup()
  
  return(df)
}


# ------------------ Cluster mode -------------------------------
# Start time
start_time <- Sys.time()

# Initialize the cluster
cl <- makeCluster(detectCores() - 15)

# Export all necessary functions and objects to the cluster
clusterExport(cl, varlist = ls()[sapply(ls(), function(x) is.function(get(x)))])

# Source the necessary file in each worker
clusterEvalQ(cl, {
  library(dplyr)
  library(readr)
  library(stringr)
})

# Split the data into chunks and process in parallel
chunk_indices <- split(seq_len(nrow(annotated_file)), sort(seq_len(nrow(annotated_file)) %% detectCores()))
chunks <- lapply(chunk_indices, function(idx) annotated_file[idx, ])

# Apply function in parallel, passing additional arguments
processed_annotated_file <- parLapply(cl, chunks, check_acmg, freq_cols, comp_cols)

# Stop the cluster
stopCluster(cl)

# Combine results into a single data frame
processed_annotated_file <- do.call(rbind, processed_annotated_file)
# End time
stop_time <- Sys.time()

# Elapsed time
elapsed_time <- stop_time - start_time
print(paste("Elapsed time: ", elapsed_time))
# ------------------ Save Annotated MAF ----------------------
# 
# output_path <- "~/path/to/file_with_acmg.maf"
# 
# write_delim(annotated_file, output_path, delim = "\t")
# 
# cat("ACMG annotation complete. Output written to:\n", output_path, "\n")
