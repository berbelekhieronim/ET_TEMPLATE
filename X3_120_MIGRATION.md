# Tobii X3-120 Migration Notes

## Date: 2026-01-25

## Overview
This branch contains modifications to support the Tobii X3-120 eye tracker (120 Hz) instead of the original Tobii Pro Spectrum (1200 Hz).

## Key Changes

### 1. Sampling Frequency
**Changed from 1200 Hz → 120 Hz**

- **Lines 180-195**: Modified eye tracker initialization to:
  - Check for 120 Hz availability (X3-120 native frequency)
  - Automatically select highest available frequency if 120 Hz not found
  - Log available frequencies for debugging
  
- **Line 51**: Increased `CALIB_DUR` from 0.20s to 0.50s
  - Rationale: At 120 Hz, 0.5s provides ~60 samples vs ~24 at 0.2s
  - Improves calibration quality with lower sampling rate

### 2. Gaze Logging Throttle
**Changed from every 1200 samples → every 120 samples**

- **Line 415**: Added `_log_interval = 120` variable
- **Line 427**: Changed throttle to use `_log_interval` instead of hardcoded 1200
- Both configurations now log approximately once per second

### 3. Documentation Updates
- Updated comments referencing 1200 Hz to reflect dynamic frequency
- Updated module docstring to reference 120 Hz throttling

## Compatibility

### What Stayed the Same (SDK Compatible):
✅ All Tobii Research SDK APIs remain identical:
- `tr.find_all_eyetrackers()`
- `tr.ScreenBasedCalibration()`
- `et.subscribe_to(tr.EYETRACKER_GAZE_DATA, ...)`
- `calib.collect_data(cx, cy)`
- `calib.compute_and_apply()`
- Gaze data structure (dictionary format)

### What Changed:
- Frequency detection and setting logic
- Calibration duration (longer to capture more samples)
- Logging throttle interval
- Comments and documentation

## Testing

### Before Running Full Experiment:
Run the test script to verify X3-120 connection:

```bash
python test_x3_120.py
```

This will verify:
- Eye tracker detection
- Available frequencies
- Model information
- Gaze data streaming capability

### Expected Output:
- Model: Should contain "X3-120" or similar
- Available Frequencies: Should include 120.0 Hz
- Gaze samples: ~240 samples in 2 seconds (120 Hz × 2s)

## Potential Issues & Solutions

### Issue 1: Lower Temporal Resolution
**Problem**: 120 Hz vs 1200 Hz = 10x fewer samples
**Impact**: 
- Fixation detection may be less stable
- Event timing less precise (8.3ms vs 0.83ms intervals)

**Mitigation**:
- Increased calibration duration to 0.5s
- Fixation tolerances unchanged (may need tuning)
- Consider increasing `FIX_DUR` if fixation detection is unstable

### Issue 2: Calibration Quality
**Problem**: Fewer samples during calibration collection
**Impact**: Potentially lower accuracy

**Mitigation**:
- Extended `CALIB_DUR` to 0.5s (60 samples vs 24)
- Monitor calibration dispersion values
- May need to increase further if quality is poor

### Issue 3: Frequency Not Available
**Problem**: X3-120 doesn't report 120 Hz as available
**Impact**: Code will use highest available frequency

**Solution**:
- Check with `test_x3_120.py`
- Manually verify frequency capabilities
- Adjust `_log_interval` accordingly

## File Changes Summary

### Modified Files:
1. `experiment_code.py`
   - Lines 18: Comment updated (1200 → 120 samples)
   - Line 51: `CALIB_DUR` increased (0.20 → 0.50)
   - Lines 180-195: Frequency detection logic
   - Line 412-415: Gaze callback comment and `_log_interval` added
   - Line 427: Throttle uses `_log_interval`

### New Files:
1. `test_x3_120.py` - Diagnostic script for X3-120
2. `X3_120_MIGRATION.md` - This document

## Validation Checklist

Before running experiments:
- [ ] Run `test_x3_120.py` successfully
- [ ] Verify X3-120 is detected with correct model name
- [ ] Confirm 120 Hz frequency is available and set
- [ ] Test gaze streaming shows ~120 samples/second
- [ ] Run calibration and verify quality metrics
- [ ] Check fixation cross detection works reliably
- [ ] Verify all data files are being created properly

## Rollback Plan

To revert to Spectrum (1200 Hz) version:
```bash
git checkout main
```

The main branch contains the original Spectrum-compatible code.

## Performance Comparison

| Metric | Spectrum (1200 Hz) | X3-120 (120 Hz) |
|--------|-------------------|-----------------|
| Sampling Rate | 1200 Hz | 120 Hz |
| Sample Interval | 0.83 ms | 8.3 ms |
| Calibration Samples (0.2s) | ~240 | ~24 |
| Calibration Samples (0.5s) | ~600 | ~60 |
| Log Interval | Every 1200 samples | Every 120 samples |
| Log Frequency | ~1/second | ~1/second |

## Support

For issues specific to X3-120:
1. Check SDK documentation in `x3-120 SDK/Tobii_Pro_SDLA_for_Research_Use.pdf`
2. Run diagnostic script: `python test_x3_120.py`
3. Review eye tracker logs in `experiment_debug.log`

## Notes

- The X3-120 SDK is located in `x3-120 SDK/64/` directory
- SDK path is added automatically by test script but not by main experiment
  - Main experiment expects system-installed tobii_research
  - For X3-120, may need to modify experiment_code.py to add SDK path

## Next Steps

If you need to add SDK path to main experiment:
```python
import sys
import os
sdk_path = os.path.join(os.path.dirname(__file__), "x3-120 SDK", "64")
sys.path.insert(0, sdk_path)
```

Add this BEFORE `import tobii_research as tr` line in experiment_code.py.
