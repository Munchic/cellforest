import os
from copy import deepcopy
from pathlib import Path
from typing import Optional, Union, List

from dataforest.core.DataForest import DataForest
from dataforest.utils.utils import label_df_partitions
import pandas as pd

from cellforest.structures.counts.Counts import Counts
from cellforest.templates.PlotMethodsSC import PlotMethodsSC
from cellforest.templates.ReaderMethodsSC import ReaderMethodsSC
from cellforest.templates.SpecSC import SpecSC
from cellforest.templates.WriterMethodsSC import WriterMethodsSC
from cellforest.utils.cellranger.DataMerge import DataMerge


class CellForest(DataForest):
    """
    DataForest for scRNAseq processed data. The `process_hierarchy` currently
    starts at `combine`, where non-normalized counts data is combined.

    A path through specific `process_runs` of processes in the
    `process_hierarchy` are specified in the `spec`, according to the
    specifications of `dataforest.Spec`. Any root level (not under a process
    name in `spec`) `subset`s or `filter`s are applied to `counts` and
    `meta`, which are the preferred methods for accessing cell metadata and
    the normalized counts matrix
    """

    PLOT_METHODS = PlotMethodsSC
    SPEC_CLASS = SpecSC
    READER_METHODS = ReaderMethodsSC
    WRITER_METHODS = WriterMethodsSC
    READER_KWARGS_MAP = {
        "reduce": {
            "pca_embeddings": {"header": "infer"},
            "pca_loadings": {"header": "infer"},
            "umap_embeddings": {"header": "infer", "index_col": 0},
        },
        "combine": {"cell_metadata": {"header": 0}},
        # 'normalize': {
        #     'cell_ids': {'index_col': 0}},
        "cluster": {"clusters": {"index_col": 0}},
        "diffexp": {"diffexp_result": {"header": 0}},
    }
    _METADATA_NAME = "meta"
    _COPY_KWARGS = {**DataForest._COPY_KWARGS, "unversioned": "unversioned"}
    _ASSAY_OPTIONS = ["rna", "vdj", "surface", "antigen", "cnv", "atac", "spatial", "crispr"]
    _DEFAULT_CONFIG = Path(__file__).parent.parent / "config/process_schema.yaml"

    def __init__(
        self, root_dir, spec=None, verbose=False, meta=None, config=None, current_process=None, unversioned=None
    ):
        super().__init__(root_dir, spec, verbose, config, current_process)
        self.assays = set()
        self._rna = None
        self._meta_unfiltered = None
        if meta is not None:
            meta = meta.copy()
        self._meta = self.get_cell_meta(meta)
        # TODO: use this to augment strings of output directories so manual tinkers don't
        #   affect downstream processing
        if meta is not None and unversioned is None:
            self._unversioned = True
        else:
            self._unversioned = bool(unversioned)
        if self.unversioned:
            self.logger.warning(f"Unversioned DataForest")

    @property
    def samples(self) -> pd.DataFrame:
        """
        Hierarchical categorization of all samples in dataset with cell counts.
        The canonical use case would be to use it on a broad DataForest to choose
        a dataset.
        Returns:

        """
        raise NotImplementedError()

    @property
    def meta(self) -> pd.DataFrame:
        """
        Interface for cell metadata, which is derived from the sample
        metadata and the scrnaseq experimental data. Available UMAP embeddings
        and cluster identifiers will be included, and the data will be subset,
        filtered, and partitioned based on the specifications in `self.spec`.
        Primarily for this reason, this is the preferred interface to metadata
        over direct file access.
        """
        # TODO: add embeddings and cluster ids
        if self._meta is None:
            self._meta = self.get_cell_meta()
        elif "reduce" in self.spec and "UMAP_1" not in self._meta.columns:
            if self["reduce"].done:
                self._meta = self.get_cell_meta()
        elif "cluster" in self.spec and "cluster_id" not in self._meta.columns:
            if self["cluster"].done:
                self._meta = self.get_cell_meta()
        return self._meta

    @property
    def rna(self) -> Counts:
        """
        Interface for normalized counts data. It uses the `Counts` wrapper
        around `scipy.sparse.csr_matrix`, which allows for slicing with
        `cell_id`s and `gene_name`s.
        """
        if self._rna is None:
            # TODO: set to use normalized if exists by default -- see old version
            # TODO: soft code filenames
            counts_path = self.root_dir / "rna.pickle"
            if not counts_path.exists():
                raise FileNotFoundError(
                    f"Ensure that you initialized the root directory with CellForest.from_metadata or "
                    f"CellForest.from_input_dirs. Not found: {counts_path}"
                )
            self._rna = Counts.load(counts_path)
        if not self._rna.index.equals(self.meta.index):
            self._rna = self._rna[self.meta.index]
        return self._rna

    @property
    def vdj(self):
        raise NotImplementedError()

    @property
    def surface(self):
        raise NotImplementedError()

    @property
    def antigen(self):
        raise NotImplementedError()

    @property
    def cnv(self):
        raise NotImplementedError()

    @property
    def atac(self):
        raise NotImplementedError()

    @property
    def spatial(self):
        raise NotImplementedError()

    @property
    def crispr(self):
        raise NotImplementedError()

    def groupby(self, by: Union[str, list, set, tuple], **kwargs):
        """
        Operates like a pandas groupby, but does not return a GroupBy object,
        and yields (name, DataForest), where each DataForest is subset according to `by`,
        which corresponds to columns of `self.meta`.
        This is useful for batching analysis across various conditions, where
        each run requires an DataForest.
        Args:
            by: variables over which to group (like pandas)
            **kwargs: for pandas groupby on `self.meta`

        Yields:
            name: values for DataForest `subset` according to keys specified in `by`
            forest: new DataForest which inherits `self.spec` with additional `subset`s
                from `by`
        """
        raise NotImplementedError("currently not functioning")
        if isinstance(by, (tuple, set)):
            by = list(by)
        for (name, df) in self.meta.groupby(by, **kwargs):
            if isinstance(by, list):
                if isinstance(name, (list, tuple)):
                    subset_dict = dict(zip(by, name))
                else:
                    subset_dict = {by[0]: name}
            else:
                subset_dict = {by: name}
            forest = self.get_subset(subset_dict)
            # forest._meta = df
            yield name, forest

    @property
    def unversioned(self):
        return self._unversioned

    def copy(self, reset: bool = False, **kwargs):
        if kwargs.get("meta", None) is not None:
            kwargs["unversioned"] = True
        if not kwargs:
            kwargs["meta"] = self._meta  # save compute if no modifications
        base_kwargs = self._get_copy_base_kwargs()
        kwargs = {**base_kwargs, **kwargs}
        kwargs = {k: deepcopy(v) for k, v in kwargs.items()}
        if reset:
            kwargs = base_kwargs
        return self.__class__(**kwargs)

    @property
    def meta_unfiltered(self) -> pd.DataFrame:
        # TODO: not used anywhere, figure out use and add docstring or delete
        return self._meta_unfiltered

    def set_partition(self, process_name: Optional[str] = None, encodings=True):
        """Add columns to metadata to indicate partition from spec"""
        columns = self.spec[process_name]["partition"]
        self._meta = label_df_partitions(self.meta, columns, encodings)

    def get_cell_meta(self, df=None):
        # TODO: MEMORY DUPLICATION - we want to keep file access pure?
        if df is None:
            # TODO: fix this
            try:
                # df = self.f["cell_metadata"].copy()
                df = pd.read_csv(self.root_dir / "meta.tsv", sep="\t", index_col=0)
            except FileNotFoundError:
                df = pd.DataFrame(self.rna.cell_ids.copy())
                df.columns = ["cell_id"]
                df.index = df["cell_id"]
                df.drop(columns=["cell_id"], inplace=True)
            df.replace(" ", "_", regex=True, inplace=True)
            if "to_bucket_var" in df and "bucketed_var" not in df:
                df["bucketed_var"] = pd.cut(df["to_bucket_var"], bins=(0, 20, 40, 60, 80), labels=(10, 30, 50, 70),)
            if "str_var_preprocessed" in df and "str_var_processed" not in df:
                df["str_var_processed"] = df["str_var_preprocessed"].str.extract(r"([A-Z]\d)")
            # TODO: fill in once `process_run.done` feature is ready
            df = self._meta_add_downstream_data(df)
        partitions_list = self.spec.get_partition_list(self.current_process)
        partitions = set().union(*partitions_list)
        if partitions:
            df = label_df_partitions(df, partitions, encodings=True)
        return df

    def _meta_add_downstream_data(self, df):
        done = set()
        if "cluster" in self.spec:
            if self["cluster"].done:
                done.update({"normalize", "reduce", "cluster"})
        if not done and "reduce" in self.spec:
            if self["reduce"].done:
                done.update({"normalize", "reduce"})
        if not done and "normalize" in self.spec:
            if self["normalize"].done:
                done.update({"normalize"})
        # if "cluster" in done:
        #     clusters = self.f["cluster"]["clusters"].copy()
        #     clusters.rename(columns={1: "cluster_id"}, inplace=True)
        #     df = df.merge(clusters, how="left", left_index=True, right_index=True)
        #     df["cluster_id"] = df["cluster_id"].astype(pd.Int16Dtype())
        # if "reduce" in done:
        #     df = df.merge(self.f["reduce"]["umap_embeddings"], how="left", left_index=True, right_index=True)
        # if "normalize" in done:
        #     pass
        #     # df = df[df.index.isin(self.f["normalize"]["cell_ids"][0])]
        # # TODO: temp during param mismatch
        # try:
        #     df = df[df.index.isin(self.f["normalize"]["cell_ids"][0])]
        # except Exception:
        #     self.logger.info("Could not find filtered cell ids. Using all cells in metadata")
        return df

    @staticmethod
    def _combine_datasets(
        root_dir: Union[str, Path],
        metadata: Optional[Union[str, Path, pd.DataFrame]] = None,
        input_paths: Optional[List[Union[str, Path]]] = None,
        metadata_read_kwargs: Optional[dict] = None,
        mode: Optional[str] = None,
    ):
        """
        Combine files from multiple cellranger output directories into a single
        `Counts` and save it to `root_dir`. If sample metadata is provided,
        replicate each row corresponding to the number of cells in the sample
        such that the number of rows changes from n_samples to n_cells.
        """
        root_dir = Path(root_dir)
        mode = mode if mode else "rna"
        if (input_paths and metadata) or (input_paths is None and metadata is None):
            raise ValueError("Must specify exactly one of `input_dirs` or `metadata`")
        elif metadata is not None:
            if isinstance(metadata, (str, Path)):
                metadata_read_kwargs = {"sep": "\t"} if not metadata_read_kwargs else metadata_read_kwargs
                metadata = pd.read_csv(metadata, **metadata_read_kwargs)
            prefix = "path_"
            assays = [x[len(prefix) :] for x in metadata.columns if x.startswith(prefix)]
            if len(assays) == 0:
                raise ValueError(
                    f"metadata must contain at least once column named with the prefix, `path_`, and one of the "
                    f"following assays as a suffix: {CellForest._ASSAY_OPTIONS}"
                )
            for assay in assays:
                paths = metadata[f"{prefix}{assay}"].tolist()
                DataMerge.merge_assay(paths, assay, metadata, save_dir=root_dir)
        else:
            DataMerge.merge_assay(input_paths, mode, save_dir=root_dir)
        return dict()

    @staticmethod
    def _get_assays(path):
        # TODO: will have to change once decoupled from pickle (e.g. rds, anndata)
        files = list(filter(lambda x: x.endswith(".pickle"), os.listdir(path)))
        return set(map(lambda x: x.split(".")[0], files))
