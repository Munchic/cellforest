args <- commandArgs(trailingOnly = TRUE)

input_metadata_path <- args[1]
input_rds_path <- args[2]
output_rds_path <- args[3]
min_genes <- as.numeric(args[4])
max_genes <- as.numeric(args[5])
min_cells <- as.numeric(args[6])
perc_mito_cutoff <- as.numeric(args[7])
r_functions_filepath <- args[8]

verbose <- as.logical(args[9])
nfeatures <- as.numeric(args[10])

source(r_functions_filepath)


print("creating Seurat object")
srat <- readRDS(input_rds_path)
print("reading metadata"); print(date())
meta <- read.table(input_metadata_path, sep = "\t", header = TRUE, row.names = 1)
print("metadata filter"); print(date())
srat <- metadata_filter_objs(meta, srat)
print("filtering cells"); print(date())
srat <- filter_cells(srat, min_genes, max_genes, perc_mito_cutoff)
print("normalizing"); print(date())
srat <- NormalizeData(srat, verbose = verbose)
print("finding variable features"); print(date())
srat <- FindVariableFeatures(srat, selection.method = "vst", nfeatures = nfeatures)
print("scaling data"); print(date())
srat <- ScaleData(srat, verbose = verbose)
print("Saving output object"); print(date())
saveRDS(srat, file = output_rds_path)
print("default Seurat normalization DONE"); print(date())
