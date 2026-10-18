"""Set de facturas simuladas y evaluación del agente (ver dataset/README.md)."""
from pathlib import Path

DATASET_DIR = Path(__file__).resolve().parents[3] / "dataset"
MANIFEST = DATASET_DIR / "manifest.json"
INVOICES_DIR = DATASET_DIR / "invoices"
RESULTS_DIR = DATASET_DIR / "results"
