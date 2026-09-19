from __future__ import annotations

import pytest
import pandas as pd
from pathlib import Path

from app.providers.bts_t100 import BtsT100FileProvider

class TestBtsT100FileProvider:
    @pytest.fixture
    def mock_csv(self, tmp_path: Path) -> Path:
        data = """ORIGIN,DEST,DISTANCE,DEPARTURES_PERFORMED,YEAR,MONTH,CLASS
ANC,SEA,1500,80,2025,1,F
ANC,NRT,3500,20,2025,1,F
SEA,ANC,1500,80,2025,1,F
BOS,LHR,3200,50,2025,1,F
ZZZ,YYY,1000,10,2025,1,F
"""
        p = tmp_path / "test_t100.csv"
        p.write_text(data)
        return tmp_path

    def test_load_and_index(self, mock_csv: Path) -> None:
        provider = BtsT100FileProvider(path=mock_csv)
        
        assert provider.is_loaded()
        assert "ANC" in provider._by_origin
        assert "BOS" in provider._by_origin
        assert "SEA" not in provider._by_origin  # Not in SUPPORTED
        assert "ZZZ" not in provider._by_origin  # Not in SUPPORTED
        
        anc_df = provider._by_origin["ANC"]
        assert len(anc_df) == 2
        assert "distance_miles" in anc_df.columns
        assert "performed_departures" in anc_df.columns

    @pytest.mark.asyncio
    async def test_fetch(self, mock_csv: Path) -> None:
        provider = BtsT100FileProvider(path=mock_csv)
        outcome = await provider.fetch(["ANC", "BOS", "JFK"])
        
        assert "ANC" in outcome.fields
        assert outcome.fields["ANC"]["total_departures"].value == 100
        assert outcome.fields["ANC"]["long_haul_flights"].value == 20
        
        assert "BOS" in outcome.fields
        assert outcome.fields["BOS"]["total_departures"].value == 50
        assert outcome.fields["BOS"]["long_haul_flights"].value == 50
        
        assert "JFK" not in outcome.fields

    def test_get_report(self, mock_csv: Path) -> None:
        provider = BtsT100FileProvider(path=mock_csv)
        report = provider.get_report("ANC")
        
        assert report["airport"] == "ANC"
        assert report["total_departures"] == 100.0
        assert report["long_haul_departures"] == 20.0
        assert report["percentage"] == 20.0
