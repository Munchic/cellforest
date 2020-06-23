from functools import wraps

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix


class Counts(csr_matrix):
    SUPER_METHODS = [
        "arcsin",
        "arcsinh",
        "arctan",
        "arctanh",
        "asformat",
        "asfptype",
        "astype",
        "ceil",
        "conj",
        "conjugate",
        "copy",
        "deg2rad",
        "eliminate_zeros",
        "expm1",
        "floor",
        "log1p",
        "maximum",
        "minimum",
        "multiply",
        "power",
        "rad2deg",
        "rint",
        "sign",
        "sin",
        "sinh",
        "sqrt",
        "tan",
        "tanh",
        "trunc",
    ]

    def __init__(self, matrix, cell_ids, features, **kwargs):
        # TODO: make a get_counts function that just takes the directory
        super().__init__(matrix, **kwargs)
        self.matrix = matrix
        self.features = features
        cell_ids = self._to_series(cell_ids)
        genes = self._to_series(features, 1)
        ensgs = self._to_series(features, 0)
        self._idx = cell_ids.copy()
        self._ids = cell_ids.copy()
        self._ids = self._index_col_swap(self._ids)
        self._genes_idx = genes.copy()
        self._ensgs_idx = ensgs.copy()
        self._genes_names = self._index_col_swap(genes.copy(), 1)
        self._ensgs_names = self._index_col_swap(ensgs.copy(), 0)

    @property
    def index(self):
        return self._idx

    @property
    def columns(self):
        return self._genes_idx

    @property
    def cell_ids(self):
        return self.index

    @property
    def genes(self):
        return self.columns

    @property
    def ensgs(self):
        return self._ensgs_idx

    def vstack(self, other):
        raise NotImplementedError()

    def hstack(self, other):
        raise NotImplementedError()

    def to_df(self):
        return pd.DataFrame(self.todense(), columns=self.columns, index=self.index)

    def dropna(self, axis=None):
        if axis is None:
            return self.dropna(axis=0).dropna(axis=1)
        sum_axis = int(not bool(axis))
        selector = np.asarray(self.sum(axis=sum_axis)).flatten().astype(bool)
        if axis == 0:
            return self[selector]
        else:
            return self[:, selector]

    def __getitem__(self, key):
        genes = self._genes_idx
        ensgs = self._ensgs_idx
        if isinstance(key, tuple):
            gene_sliced = self._gene_slice(key[1])

            cell_sliced = gene_sliced[key[0]]
            return cell_sliced
        key = self._convert_key(key, self._ids)
        if isinstance(key, slice):
            cell_ids = pd.DataFrame(self._idx[key]).reset_index(drop=True)
        else:
            cell_ids = pd.DataFrame(self._idx.reindex(key)).reset_index(drop=True)
        mat = csr_matrix(self.matrix)[key]
        return self.__class__(mat, cell_ids, genes)

    def _gene_slice(self, key):
        """Slice columns with either gene names or ensemble gene names"""
        key = self._convert_key(key, self._genes_names)
        genes = pd.DataFrame(self._genes_idx.reindex(key)).reset_index(drop=True)
        ensgs = pd.DataFrame(self._ensgs_idx.reindex(key)).reset_index(drop=True)
        mat = csr_matrix(self.matrix)[:, key]
        col_slice = genes if len(genes) > len(ensgs) else ensgs
        return self.__class__(mat, self._idx, col_slice)

    @staticmethod
    def _convert_key(key, df):
        if isinstance(key, (pd.Series, pd.Index, np.ndarray)):
            key = key.tolist()
        if isinstance(key, list):
            if isinstance(key[0], str):
                key = df.reindex(key).dropna()["i"].astype(int).tolist()
        elif isinstance(key, str):
            key = [df.loc[key]["i"].tolist()]
        elif isinstance(key, int):
            key = [key]
        return key

    @staticmethod
    def _check_key(key, df):
        """
        NOTE: not currently used because metedata includes cells that were filtered out by cellranger
        """
        intersection = len(set(key).intersection(set(df.index.tolist()))) / len(key)
        if intersection < 1:
            import ipdb

            ipdb.set_trace()
            raise KeyError(f"some of provided keys missing from counts matrix. Intersection: {intersection}")

    def __repr__(self):
        return f"{self.__class__}: [cell_ids x genes] matrix\n" + csr_matrix.__repr__(self)

    @staticmethod
    def _index_col_swap(df, col=0, new_index_colname="i"):
        """Swaps column with index of DataFrame"""
        df = df.copy()
        if isinstance(df, pd.Series):
            df = pd.DataFrame(df)
        df[new_index_colname] = df.index
        try:
            df.index = df[col]
        except:
            pass
        try:
            df.drop(columns=col, inplace=True)
        except:
            pass
        return df

    @staticmethod
    def _to_series(df, col_ind=0):
        df = df.copy()
        if isinstance(df, pd.DataFrame):
            df = df.iloc[:, col_ind]
        return df

    @staticmethod
    def wrap_super(func):
        @wraps(func)
        def wrapper(counts, *args, **kwargs):
            matrix = func(counts.matrix, *args, **kwargs)
            return counts.__class__(matrix, counts.cell_ids, counts.genes)

        return wrapper

    @staticmethod
    def decorate(method_names):
        for name in method_names:
            super_method = getattr(csr_matrix, name)
            wrapped_method = Counts.wrap_super(super_method)
            setattr(Counts, name, wrapped_method)


Counts.decorate(Counts.SUPER_METHODS)