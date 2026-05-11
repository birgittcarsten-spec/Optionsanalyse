"""Serialisierung und Deserialisierung von Plattform-Daten.

Unterstützt JSON- und Parquet-Formate mit automatischer Metadaten-Verwaltung.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


@dataclass
class DataEnvelope:
    """Wrapper für persistierte Daten mit Metadaten."""

    data: pd.DataFrame
    timestamp: datetime
    version: str
    data_type: str


class SerializationService:
    """Serialisierung und Deserialisierung von Plattform-Daten."""

    SCHEMA_VERSION = "1"

    def __init__(self, base_path: Path, version: str = "1.0.0"):
        self.base_path = Path(base_path)
        self.version = version

    def serialize(self, envelope: DataEnvelope, format: str = "parquet") -> Path:
        """Daten serialisieren und speichern."""
        if format not in ("json", "parquet"):
            raise ValueError(f"Ungültiges Format: {format}. Erlaubt: 'json', 'parquet'")

        if envelope.timestamp is None:
            envelope.timestamp = datetime.now(timezone.utc)

        if not envelope.version:
            envelope.version = self.version

        self.base_path.mkdir(parents=True, exist_ok=True)

        timestamp_str = envelope.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"{envelope.data_type}_{timestamp_str}"

        if format == "json":
            path = self.base_path / f"{filename}.json"
            self._serialize_to_json(envelope, path)
        else:
            path = self.base_path / f"{filename}.parquet"
            self._serialize_to_parquet(envelope, path)

        return path

    def deserialize(self, path: Path) -> DataEnvelope:
        """Gespeicherte Daten laden und deserialisieren."""
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Datei nicht gefunden: {path}")

        suffix = path.suffix.lower()
        if suffix == ".json":
            return self._deserialize_from_json(path)
        elif suffix == ".parquet":
            return self._deserialize_from_parquet(path)
        else:
            raise ValueError(f"Unbekanntes Dateiformat: {suffix}. Erlaubt: '.json', '.parquet'")

    def _serialize_to_json(self, envelope: DataEnvelope, path: Path) -> None:
        """DataFrame als JSON mit Metadaten speichern."""
        output = {
            "metadata": {
                "timestamp": envelope.timestamp.isoformat(),
                "version": envelope.version,
                "data_type": envelope.data_type,
                "schema_version": self.SCHEMA_VERSION,
            },
            "data": json.loads(envelope.data.to_json(orient="records", date_format="iso")),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    def _serialize_to_parquet(self, envelope: DataEnvelope, path: Path) -> None:
        """DataFrame als Parquet mit Metadaten speichern."""
        table = pa.Table.from_pandas(envelope.data)

        metadata = {
            b"timestamp": envelope.timestamp.isoformat().encode(),
            b"version": envelope.version.encode(),
            b"data_type": envelope.data_type.encode(),
            b"schema_version": self.SCHEMA_VERSION.encode(),
        }

        existing_metadata = table.schema.metadata or {}
        merged_metadata = {**existing_metadata, **metadata}
        table = table.replace_schema_metadata(merged_metadata)

        pq.write_table(table, path)

    def _deserialize_from_json(self, path: Path) -> DataEnvelope:
        """JSON-Datei laden und in DataEnvelope umwandeln."""
        with open(path, "r", encoding="utf-8") as f:
            content = json.load(f)

        metadata = content["metadata"]
        data = pd.DataFrame(content["data"])

        timestamp = datetime.fromisoformat(metadata["timestamp"])

        return DataEnvelope(
            data=data,
            timestamp=timestamp,
            version=metadata["version"],
            data_type=metadata["data_type"],
        )

    def _deserialize_from_parquet(self, path: Path) -> DataEnvelope:
        """Parquet-Datei laden und in DataEnvelope umwandeln."""
        table = pq.read_table(path)
        schema_metadata = table.schema.metadata or {}

        data = table.to_pandas()

        timestamp_str = schema_metadata.get(b"timestamp", b"").decode()
        timestamp = datetime.fromisoformat(timestamp_str)

        version = schema_metadata.get(b"version", b"").decode()
        data_type = schema_metadata.get(b"data_type", b"").decode()

        return DataEnvelope(
            data=data,
            timestamp=timestamp,
            version=version,
            data_type=data_type,
        )
