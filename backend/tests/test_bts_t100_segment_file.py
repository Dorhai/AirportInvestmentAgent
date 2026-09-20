import pytest
import csv
import zipfile
from pathlib import Path
from app.providers.bts_t100_segment_file import BtsT100SegmentFileProvider

def test_bts_t100_segment_file_csv(tmp_path: Path):
    csv_path = tmp_path / "data.csv"
    with open(csv_path, "w", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ORIGIN", "DEST", "DISTANCE", "DEPARTURES_PERFORMED", "PASSENGERS", "YEAR", "MONTH", "CLASS"])
        writer.writerow(["BOS", "JFK", "187", "100", "10000", "2023", "1", "F"])
        writer.writerow(["BOS", "LHR", "3265", "30", "6000", "2023", "1", "F"])
        writer.writerow(["JFK", "LHR", "3451", "50", "10000", "2023", "1", "F"])
        
    provider = BtsT100SegmentFileProvider(csv_path)
    provider.load_sync()
    
    assert provider.is_loaded
    assert provider.period_label == "2023-01..2023-01"
    
    bos_rows = provider.rows_for("BOS")
    assert len(bos_rows) == 2
    assert bos_rows[0].dest == "JFK"
    assert bos_rows[1].dest == "LHR"
    
    jfk_rows = provider.rows_for("JFK")
    assert len(jfk_rows) == 1
    assert jfk_rows[0].dest == "LHR"

def test_bts_t100_segment_file_zip(tmp_path: Path):
    zip_path = tmp_path / "data.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("data.csv", "ORIGIN,DEST,DISTANCE,DEPARTURES_PERFORMED,PASSENGERS,YEAR,MONTH,CLASS\nBOS,JFK,187,100,10000,2023,1,F\n")
        
    provider = BtsT100SegmentFileProvider(zip_path)
    provider.load_sync()
    
    assert provider.is_loaded
    assert len(provider.rows_for("BOS")) == 1

def test_bts_t100_segment_file_missing(tmp_path: Path):
    provider = BtsT100SegmentFileProvider(tmp_path / "missing.csv")
    provider.load_sync()
    
    assert not provider.is_loaded
    assert provider.period_label is None
    assert len(provider.rows_for("BOS")) == 0
