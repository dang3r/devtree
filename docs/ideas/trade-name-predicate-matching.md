# Idea: Trade Name to K-Number Predicate Matching

## Problem

~29% of devices (25,899) don't have K-number predicates extracted from their PDFs. Analysis of 10 such devices revealed:

- **8/10** reference predicates by trade name only (e.g., "Canon R-50m", "Paramount Cemented Hip Stem")
- **2/10** reference pre-1976 devices or use generic language

The regex `K\d{6}` correctly extracts K-numbers, but many PDFs simply don't contain them.

## Proposed Solution

Use the FDA 510(k) database (`device-510k-0001-of-0001.json`) to build a trade name → K-number mapping.

### Data Available

- `device-510k-0001-of-0001.json`: 173,584 devices with `device_name` and `k_number` fields
- 159,446 unique device names

### Approach: Fuzzy Matching

Using `rapidfuzz` library for fuzzy string matching:

```python
from rapidfuzz import fuzz, process

# Build index
devices = {item['device_name']: item['k_number'] for item in data['results']}

# Fuzzy match
matches = process.extract(trade_name, device_names, scorer=fuzz.token_set_ratio, limit=3)
```

### Test Results

| Trade Name (from PDF) | Best Match | Score | K-Number |
|----------------------|------------|-------|----------|
| Swanson Tendon Spacer | Universal Tendon Spacer | 76% | K243477 |
| Paramount Cemented Hip Stem | Cemented TSI Hip Stem | 89% | K192024 |
| DePuy Quantum Hip Stem | Quantum LB | 82% | K161684 |
| Elecsys CalCheck TSH | Elecsys TSH | 100% | K190773 |

### Challenges

1. **Temporal mismatch**: Fuzzy matching finds similar-named devices, not necessarily the actual predicate (which may be from a different era)
2. **Different manufacturers**: "Paramount Cemented Hip Stem" (DePuy, ~2000) matched to "Cemented TSI Hip Stem" (different company, 2019)
3. **Pre-1976 devices**: Some predicates predate the 510(k) system entirely

### Potential Improvements

1. **High-threshold matching (≥90%)**: Only accept very confident matches
2. **Applicant-aware matching**: Match within same company (DePuy → DePuy devices only)
3. **LLM extraction**: Use LLM to extract trade names from PDFs and validate relationships
4. **Confidence scoring**: Store matches with confidence scores as "possible predicates"

## Files Involved

- `device-510k-0001-of-0001.json` - FDA 510(k) database (1.6GB)
- `predicates.json` - Current extraction results
- `text/*.txt` - Cached PDF text for re-analysis

## Dependencies Added

- `rapidfuzz` - For fuzzy string matching

## Status

Parked for future exploration. Current predicate extraction covers 71% of devices with high confidence.
