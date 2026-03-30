# Troubleshooting Eye Tracker Connection

## Quick Diagnostics

If the experiment doesn't connect to the eye tracker, run this diagnostic script first:

```bash
python debug_import.py
```

This will show you exactly where the connection is failing.

## Common Issues

### 1. "No eye trackers found"

**Symptoms:**
- Script runs but shows "No eye-tracker found" warning
- TOBII["connected"] = False

**Solutions:**
1. **Check physical connection:**
   - USB cable properly connected
   - Eye tracker powered on
   - Try different USB port (preferably USB 3.0)

2. **Check drivers:**
   - Windows: Open Device Manager, look for Tobii devices
   - If no Tobii devices shown, drivers may not be installed
   - Install Tobii Eye Tracker drivers from Tobii website

3. **Check for conflicts:**
   - Close Tobii Studio if running
   - Close any other eye tracking software
   - Restart the eye tracker

4. **Test with Tobii software:**
   - If you have Tobii Studio or other Tobii apps, test connection there first
   - If they can't see it either, it's a hardware/driver issue

### 2. "Import tobii_research failed"

**Symptoms:**
- Error when importing tobii_research module
- Script crashes before even searching for trackers

**Solutions:**

#### On Windows:
The X3-120 SDK should work if:
- You're on 64-bit Windows
- Python is 64-bit (check with `python -c "import sys; print(sys.maxsize > 2**32)"`)
- The .pyd file is compatible with your Python version

If still failing:
```bash
# Install system-wide tobii-research
pip install tobii-research
```

#### On Linux/Mac:
The included SDK is Windows-only (.pyd files). You must install system package:
```bash
pip install tobii-research
```

Then **remove** or **comment out** the SDK path lines in experiment_code.py:
```python
# X3_SDK_PATH = os.path.join(HERE, "x3-120 SDK", "64")
# if os.path.exists(X3_SDK_PATH) and X3_SDK_PATH not in sys.path:
#     sys.path.insert(0, X3_SDK_PATH)
```

### 3. SDK version mismatch

**Symptoms:**
- Module loads but crashes when calling functions
- "DLL load failed" or similar errors

**Solution:**
Use system-wide installation instead of bundled SDK:
```bash
pip install tobii-research
```

And modify experiment_code.py to skip the local SDK (comment out lines 172-177).

## Testing Steps

### Step 1: Run Diagnostic
```bash
python debug_import.py
```

Expected output if working:
```
✓ Import successful!
SDK Version: 1.x.x
✓ Found 1 eye tracker(s)
Eye Tracker #1:
  Model: Tobii X3-120
  ...
```

### Step 2: Run Test Script
```bash
python test_x3_120.py
```

This tests:
- Connection
- Frequency settings
- Gaze data streaming

### Step 3: Check Logs
If experiment runs but doesn't connect, check:
```
experiment_debug.log
```

Look for lines like:
- "Added X3-120 SDK to path" ✓
- "Tobii Research SDK loaded" ✓
- "Connected to [serial] ([model])" ✓
- "Available frequencies: [...]" ✓

If you see:
- "No eye-tracker found" → Hardware/driver issue
- Exception during import → SDK/Python compatibility issue

## Platform-Specific Notes

### Windows (Recommended)
- Use bundled SDK (x3-120 SDK/64/)
- Requires 64-bit Python
- .pyd files must match Python version

### Linux
- Remove bundled SDK from path
- Install: `pip install tobii-research`
- May need libusb: `sudo apt install libusb-1.0-0`

### macOS
- Remove bundled SDK from path
- Install: `pip install tobii-research`
- May need additional USB permissions

## Still Not Working?

1. **Verify Python architecture:**
   ```bash
   python -c "import struct; print(struct.calcsize('P') * 8)"
   ```
   Should print: `64`

2. **Check Python version:**
   ```bash
   python --version
   ```
   SDK supports Python 3.7+

3. **Try system install:**
   ```bash
   pip uninstall tobii-research
   pip install tobii-research
   ```

4. **Check if it's a hardware issue:**
   - Test with Tobii's official software
   - Try on different computer
   - Check USB cable

## Contact Support

If none of the above works, provide this information:
1. Output of `python debug_import.py`
2. Output of `python --version`
3. Operating system and version
4. Content of `experiment_debug.log`
5. Eye tracker model (from device label)
