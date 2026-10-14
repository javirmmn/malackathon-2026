"""Segmentación de clientes: tipos -> variables -> preprocesado -> búsqueda de modelos -> perfiles.

Funciona con cualquier tabla de clientes (una fila por cliente). Lo específico del reto
se ajusta con parámetros (columnas a excluir, rango de k, escalado...), no tocando código.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.cluster import HDBSCAN, KMeans
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler, StandardScaler

from common.dataio import coerce_types  # noqa: F401  (se reexporta: pl.coerce_types)

_ID_NAME = re.compile(r"(^id$|^id_|_id$|^cod|codigo|dni|nif|email|correo|telefono|movil|nombre|apellido|direccion)", re.I)


@dataclass
class Schema:
    numeric: list[str] = field(default_factory=list)
    categorical: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    dropped: dict[str, str] = field(default_factory=dict)

    def as_rows(self) -> pd.DataFrame:
        rows = [(c, "numérica") for c in self.numeric] + [(c, "categórica") for c in self.categorical]
        rows += [(c, "fecha -> días desde") for c in self.dates]
        rows += [(c, f"descartada: {m}") for c, m in self.dropped.items()]
        return pd.DataFrame(rows, columns=["columna", "uso"])


def infer_schema(df: pd.DataFrame, exclude: tuple[str, ...] = (), max_categories: int = 30) -> Schema:
    sch = Schema()
    n = len(df)
    for c in df.columns:
        s = df[c]
        if c in exclude or c.startswith("_"):
            sch.dropped[c] = "excluida"
        elif s.isna().mean() > 0.6:
            sch.dropped[c] = "más del 60 % de nulos"
        elif s.nunique(dropna=True) <= 1:
            sch.dropped[c] = "constante"
        elif pd.api.types.is_datetime64_any_dtype(s):
            sch.dates.append(c)
        elif pd.api.types.is_bool_dtype(s):
            sch.categorical.append(c)
        elif pd.api.types.is_numeric_dtype(s):
            if _ID_NAME.search(c) and s.nunique() > 0.9 * n:
                sch.dropped[c] = "parece un identificador"
            else:
                sch.numeric.append(c)
        elif _ID_NAME.search(c) or s.nunique() > 0.9 * n:
            sch.dropped[c] = "parece un identificador o texto libre"
        elif s.nunique() > max_categories:
            sch.dropped[c] = f"texto con {s.nunique()} categorías (> {max_categories})"
        else:
            sch.categorical.append(c)
    return sch


def build_features(df: pd.DataFrame, sch: Schema, ref_date: pd.Timestamp | None = None) -> tuple[pd.DataFrame, list[str], pd.Timestamp | None]:
    """Tabla de variables para el modelo. Las fechas pasan a 'dias_desde_<col>' (tipo recencia de RFM)."""
    X = df[sch.numeric + sch.categorical].copy()
    num_cols = list(sch.numeric)
    if sch.dates:
        ref_date = ref_date or max(df[c].max() for c in sch.dates)
        for c in sch.dates:
            name = f"dias_desde_{c}"
            X[name] = (ref_date - df[c]).dt.days.astype("float")
            num_cols.append(name)
    for c in sch.categorical:
        X[c] = X[c].map(lambda v: np.nan if pd.isna(v) else str(v)).astype(object)
    return X, num_cols, ref_date


# --------------------------------------------------------------------------- preprocesado
class Winsorizer(BaseEstimator, TransformerMixin):
    """Recorta valores atípicos a los percentiles [lower, upper] aprendidos en el ajuste."""

    def __init__(self, lower: float = 0.01, upper: float = 0.99):
        self.lower, self.upper = lower, upper

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        self.lo_ = np.nanquantile(X, self.lower, axis=0)
        self.hi_ = np.nanquantile(X, self.upper, axis=0)
        return self

    def transform(self, X):
        return np.clip(np.asarray(X, dtype=float), self.lo_, self.hi_)

    def get_feature_names_out(self, input_features=None):
        return np.asarray(input_features, dtype=object)


def make_preprocessor(num_cols: list[str], cat_cols: list[str], scaler: str = "standard", cat_weight: float = 0.5) -> ColumnTransformer:
    """cat_weight < 1 evita que las variables one-hot dominen la distancia."""
    num = Pipeline(
        [
            ("imputar", SimpleImputer(strategy="median")),
            ("atipicos", Winsorizer()),
            ("escalar", RobustScaler() if scaler == "robust" else StandardScaler()),
        ]
    )
    cat = Pipeline(
        [
            ("imputar", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False, min_frequency=0.01)),
        ]
    )
    parts, weights = [("num", num, num_cols)], {"num": 1.0}
    if cat_cols:
        parts.append(("cat", cat, cat_cols))
        weights["cat"] = cat_weight
    return ColumnTransformer(parts, transformer_weights=weights, verbose_feature_names_out=False)


# --------------------------------------------------------------------------- modelos
def _metrics(Z: np.ndarray, labels: np.ndarray, seed: int) -> dict:
    mask = labels >= 0
    k = len(set(labels[mask]))
    out = {"n_clusters": k, "ruido_pct": round(100 * (1 - mask.mean()), 1)}
    if k < 2:
        return out | {"silhouette": np.nan, "davies_bouldin": np.nan, "calinski_harabasz": np.nan}
    Zm, lm = Z[mask], labels[mask]
    sample = min(3000, len(Zm))
    out["silhouette"] = round(float(silhouette_score(Zm, lm, sample_size=sample, random_state=seed)), 4)
    out["davies_bouldin"] = round(float(davies_bouldin_score(Zm, lm)), 4)
    out["calinski_harabasz"] = round(float(calinski_harabasz_score(Zm, lm)), 1)
    return out


def search_models(
    Z: np.ndarray,
    k_range: range = range(2, 11),
    seed: int = 42,
    X_raw: pd.DataFrame | None = None,
    num_cols: list[str] | None = None,
    cat_cols: list[str] | None = None,
    kprototypes: bool = False,
) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    """Prueba K-Means y GMM para cada k, HDBSCAN y (opcional) K-Prototypes. Métricas en el espacio Z."""
    rows, labels = [], {}
    for k in k_range:
        km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(Z)
        key = f"kmeans_k{k}"
        labels[key] = km.labels_
        rows.append({"modelo": key, "metodo": "K-Means", "k": k, "inercia": round(float(km.inertia_), 1)} | _metrics(Z, km.labels_, seed))

        gm = GaussianMixture(n_components=k, covariance_type="full", n_init=2, random_state=seed).fit(Z)
        key = f"gmm_k{k}"
        labels[key] = gm.predict(Z)
        rows.append({"modelo": key, "metodo": "GMM", "k": k, "bic": round(float(gm.bic(Z)), 1)} | _metrics(Z, labels[key], seed))

    min_size = max(10, len(Z) // 50)
    hd = HDBSCAN(min_cluster_size=min_size, min_samples=5, copy=True).fit(Z)
    labels["hdbscan"] = hd.labels_
    rows.append({"modelo": "hdbscan", "metodo": "HDBSCAN", "k": np.nan} | _metrics(Z, hd.labels_, seed))

    if kprototypes and X_raw is not None and cat_cols:
        from kmodes.kprototypes import KPrototypes

        num_cols = num_cols or []
        data = X_raw[num_cols + cat_cols].copy()
        data[num_cols] = data[num_cols].fillna(data[num_cols].median())
        data[num_cols] = (data[num_cols] - data[num_cols].mean()) / data[num_cols].std(ddof=0).replace(0, 1)
        for c in cat_cols:
            data[c] = data[c].fillna("NA").astype(str)
        cat_idx = list(range(len(num_cols), len(num_cols) + len(cat_cols)))
        for k in k_range:
            kp = KPrototypes(n_clusters=k, init="Cao", n_init=3, random_state=seed, n_jobs=1)
            lab = kp.fit_predict(data.to_numpy(dtype=object), categorical=cat_idx)
            key = f"kprototypes_k{k}"
            labels[key] = np.asarray(lab)
            rows.append({"modelo": key, "metodo": "K-Prototypes", "k": k} | _metrics(Z, labels[key], seed))

    table = pd.DataFrame(rows)
    cols = ["modelo", "metodo", "k", "n_clusters", "silhouette", "davies_bouldin", "calinski_harabasz", "ruido_pct", "inercia", "bic"]
    return table[[c for c in cols if c in table]], labels


def choose_model(table: pd.DataFrame, min_k: int = 3, max_k: int = 8) -> str:
    """Mejor silhouette entre los modelos con un número de segmentos 'contable' para negocio
    (min_k..max_k) y menos de un 20 % de ruido. Desempate: menor Davies-Bouldin."""
    ok = table[(table["n_clusters"].between(min_k, max_k)) & (table["ruido_pct"] < 20)].dropna(subset=["silhouette"])
    if ok.empty:
        ok = table.dropna(subset=["silhouette"])
    return ok.sort_values(["silhouette", "davies_bouldin"], ascending=[False, True]).iloc[0]["modelo"]


# --------------------------------------------------------------------------- perfiles
def centroids(Z: np.ndarray, labels: np.ndarray) -> dict[int, np.ndarray]:
    return {int(c): Z[labels == c].mean(axis=0) for c in sorted(set(labels)) if c >= 0}


def assign(Z_new: np.ndarray, cents: dict[int, np.ndarray]) -> np.ndarray:
    """Segmento del centroide más cercano (vale para cualquier método, también para clientes nuevos)."""
    keys = list(cents)
    C = np.vstack([cents[k] for k in keys])
    d = ((Z_new[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)
    return np.asarray(keys)[d.argmin(axis=1)]


def profile(X: pd.DataFrame, labels: np.ndarray, num_cols: list[str], cat_cols: list[str]) -> dict[str, pd.DataFrame]:
    """Tamaños, medias/medianas, categoría dominante y rasgos que más distinguen a cada segmento."""
    d = X.copy()
    d["segmento"] = labels
    d = d[d["segmento"] >= 0]
    sizes = d["segmento"].value_counts().sort_index().rename("clientes").to_frame()
    sizes["pct"] = (100 * sizes["clientes"] / sizes["clientes"].sum()).round(1)

    means = d.groupby("segmento")[num_cols].mean().round(2) if num_cols else pd.DataFrame()
    medians = d.groupby("segmento")[num_cols].median().round(2) if num_cols else pd.DataFrame()

    mu, sd = d[num_cols].mean(), d[num_cols].std(ddof=0).replace(0, 1)
    rasgos = []
    for seg, g in d.groupby("segmento"):
        for c in num_cols:
            z = (g[c].mean() - mu[c]) / sd[c]
            rasgos.append({"segmento": seg, "variable": c, "tipo": "numérica", "valor": round(g[c].mean(), 2),
                           "media_global": round(mu[c], 2), "diferencia": round(z, 2), "fuerza": abs(z)})
        for c in cat_cols:
            share_all = d[c].value_counts(normalize=True)
            share_seg = g[c].value_counts(normalize=True)
            for val, p in share_seg.items():
                lift = p - share_all.get(val, 0)
                if abs(lift) >= 0.1:
                    rasgos.append({"segmento": seg, "variable": f"{c} = {val}", "tipo": "categórica",
                                   "valor": round(100 * p, 1), "media_global": round(100 * share_all.get(val, 0), 1),
                                   "diferencia": round(lift, 2), "fuerza": abs(lift) * 2.5})
    rasgos = (pd.DataFrame(rasgos).sort_values(["segmento", "fuerza"], ascending=[True, False])
              .groupby("segmento").head(6).reset_index(drop=True))

    modas = {c: d.groupby("segmento")[c].agg(lambda s: s.mode().iat[0] if not s.mode().empty else None) for c in cat_cols}
    modas = pd.DataFrame(modas) if modas else pd.DataFrame()
    return {"tamanos": sizes, "medias": means, "medianas": medians, "modas": modas, "rasgos": rasgos}


def describe_trait(row: pd.Series) -> str:
    """Frase legible para un rasgo: 'ingresos_anuales muy por encima de la media (141 vs 79)'."""
    if row["tipo"] == "numérica":
        z = row["diferencia"]
        nivel = "muy por encima" if z > 1 else "por encima" if z > 0.3 else "muy por debajo" if z < -1 else "por debajo" if z < -0.3 else "en"
        return f"{row['variable']} {nivel} de la media ({row['valor']:g} vs {row['media_global']:g})"
    signo = "más" if row["diferencia"] > 0 else "menos"
    return f"{row['variable']}: {row['valor']:g} % ({signo} que el {row['media_global']:g} % global)"


def suggested_name(rasgos: pd.DataFrame, seg: int) -> str:
    top = rasgos[rasgos["segmento"] == seg].head(2)
    parts = []
    for _, r in top.iterrows():
        flecha = "↑" if r["diferencia"] > 0 else "↓"
        parts.append(f"{flecha}{r['variable']}")
    return " · ".join(parts) or f"Segmento {seg}"


# --------------------------------------------------------------------------- 2D
def embed_2d(Z: np.ndarray, seed: int = 42, umap: bool = True) -> pd.DataFrame:
    out = pd.DataFrame(PCA(n_components=2, random_state=seed).fit_transform(Z), columns=["pca_1", "pca_2"])
    if umap:
        try:
            import umap as umap_lib

            emb = umap_lib.UMAP(n_components=2, random_state=seed, n_neighbors=30, min_dist=0.1).fit_transform(Z)
            out[["umap_1", "umap_2"]] = emb
        except Exception as e:  # noqa: BLE001  (UMAP es opcional)
            print(f"[aviso] UMAP no disponible: {e}")
    return out
