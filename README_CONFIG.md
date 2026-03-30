# Experiment Configuration Guide

## How to Configure the Experiment

The experiment reads configuration from `config.txt` file in the same directory as the script.

### Configuration File Location
`config.txt` is located in the same directory as `experiment_code.py`

### Output Files Location
All binary data files (`data000.bin`, `data001.bin`, etc.) are saved to the `/output` subdirectory, which is automatically created if it doesn't exist.

## Configuration Options

### 1. Calibration Review Selection

Specify which review from the JSON file should be used for calibration:

```
CALIBRATION_REVIEW_ID=8196
```

- Use the exact review ID from `selected_reviews_data.json`
- This review will be **excluded** from the trial pool
- Default: Uses the first review in the JSON file

### 2. Number of Trials

Edit `config.txt` and modify the `N_TRIALS` value:

#### Run ALL available trials (default)
```
N_TRIALS=ALL
```

#### Run specific number of trials
```
N_TRIALS=25
```

```
N_TRIALS=50
```

### Important Notes

1. **Calibration review is excluded from trials** - The review specified by `CALIBRATION_REVIEW_ID` will NOT be included in trials
2. If you have 100 reviews in `selected_reviews_data.json`:
   - 1 review → Used for calibration (specified by `CALIBRATION_REVIEW_ID`)
   - 99 reviews → Available for trials
3. Trials are **always selected in RANDOM order** from the remaining reviews
4. If `N_TRIALS` exceeds available reviews, all available reviews will be used
5. If `config.txt` doesn't exist, it will be created automatically with default settings

### Example Scenarios

**Scenario 1: Run all trials with specific calibration review**
```
CALIBRATION_REVIEW_ID=8196
N_TRIALS=ALL
```
Result: Uses review 8196 for calibration, runs all other reviews as trials in random order

**Scenario 2: Run 25 trials with custom calibration**
```
CALIBRATION_REVIEW_ID=12345
N_TRIALS=25
```
Result: Uses review 12345 for calibration, randomly selects 25 out of remaining reviews

**Scenario 3: Run 10 trials with first review**
```
CALIBRATION_REVIEW_ID=8196
N_TRIALS=10
```
Result: Uses review 8196 for calibration, randomly selects 10 out of remaining reviews

### Finding Review IDs

To find valid review IDs, check the `selected_reviews_data.json` file. Each review has an `"id"` field:

```json
[
  {
    "id": 8196,
    "text": "Review text here...",
    ...
  },
  {
    "id": 12345,
    "text": "Another review...",
    ...
  }
]
```

### File Auto-Creation

If `config.txt` is missing or deleted, the script will automatically create it with default settings (first review for calibration, `N_TRIALS=ALL`) on the next run.
