import pytest
import os
from backend.fundamental_analysis import analyze_fundamentals

# You need to set the FMP_API_KEY environment variable for these tests to pass.
# For example: export FMP_API_KEY="YOUR_API_KEY"

@pytest.mark.skipif(os.getenv("FMP_API_KEY") is None, reason="FMP_API_KEY environment variable not set")
def test_fundamental_analysis_with_fmp_data():
    """
    Tests if analyze_fundamentals correctly fetches and uses FMP data for calculations.
    """
    ticker = "AAPL"  # Using a well-known ticker for testing
    result = analyze_fundamentals(ticker)

    assert "error" not in result, f"Fundamental analysis failed with error: {result.get('error')}"
    assert "Fundamental Score" in result
    assert "Verdict" in result
    assert "Notes" in result
    assert "Breakdown" in result

    # Check if FMP data was attempted to be fetched (even if some values are N/A)
    # This implicitly checks if the data_fetcher is calling SecondaryDataFetcher
    assert "fmp_data" in result.get("Breakdown", {}).get("Altman Z-Score", {})
    assert "fmp_data" in result.get("Breakdown", {}).get("Beneish M-Score", {})

    # Check if Altman Z-Score and Beneish M-Score are attempted to be calculated
    # They might still be N/A if FMP data is missing or invalid, but should not raise a general error
    assert result["Breakdown"].get('Altman Z-Score') is not None
    assert result["Breakdown"].get('Beneish M-Score') is not None

    # If they are N/A, ensure it's due to missing data, not a calculation error
    if result["Breakdown"].get('Altman Z-Score') == "N/A":
        assert "Altman Z: Missing non-calculable data for Z-Score." in result["Notes"]
    if result["Breakdown"].get('Beneish M-Score') == "N/A":
        assert "Beneish: Missing critical data for Beneish Score." in result["Notes"]

    print(f"\nFundamental Analysis Result for {ticker}:\n{result}")
