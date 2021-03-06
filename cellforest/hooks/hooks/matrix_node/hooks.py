from dataforest.hooks import hook

from cellforest.utils.r.Convert import Convert


@hook(attrs=["matrix_layer"])
def hook_unify_matrix_node(dp):
    """
    If node has counts matrix output, ensure that all desired formats are
    present (e.g. pickle, rds, anndata, cellranger)
    """
    # TODO: currently hardcoded to pickle and rds, but fix this later
    if dp.matrix_layer:
        pickle_path = dp.forest[dp.process_name].path_map["rna"]
        rds_path = dp.forest[dp.process_name].path_map["rna_r"]
        if pickle_path.exists() and not rds_path.exists():
            Convert.pickle_to_rds_dir(pickle_path.parent)
        elif rds_path.exists() and not pickle_path.exists():
            Convert.rds_to_pickle_dir(rds_path.parent)
