#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
debug_import.py - Debug script to test SDK import and eye tracker detection

This script helps diagnose why the eye tracker connection might be failing.
"""

import sys
import os

print("="*70)
print("DEBUG: Eye Tracker Connection Diagnostics")
print("="*70)
print()

# 1. Show Python version and platform
print(f"1. Python Environment:")
print(f"   Python Version: {sys.version}")
print(f"   Platform: {sys.platform}")
print(f"   Executable: {sys.executable}")
print()

# 2. Check if X3-120 SDK path exists
HERE = os.path.abspath(os.path.dirname(__file__))
X3_SDK_PATH = os.path.join(HERE, "x3-120 SDK", "64")
print(f"2. SDK Path Check:")
print(f"   Expected SDK path: {X3_SDK_PATH}")
print(f"   Path exists: {os.path.exists(X3_SDK_PATH)}")
if os.path.exists(X3_SDK_PATH):
    print(f"   Contents: {os.listdir(X3_SDK_PATH)}")
print()

# 3. Add SDK to path
print(f"3. Adding SDK to Python path...")
if os.path.exists(X3_SDK_PATH) and X3_SDK_PATH not in sys.path:
    sys.path.insert(0, X3_SDK_PATH)
    print(f"   ✓ Added: {X3_SDK_PATH}")
else:
    print(f"   ✗ Failed to add SDK path")
print(f"   Current sys.path (first 5):")
for i, p in enumerate(sys.path[:5]):
    print(f"     [{i}] {p}")
print()

# 4. Try importing tobii_research
print(f"4. Importing tobii_research module...")
try:
    import tobii_research as tr
    print(f"   ✓ Import successful!")
    print(f"   Module location: {tr.__file__}")
    print(f"   SDK Version: {tr.__version__}")
except ImportError as e:
    print(f"   ✗ Import failed!")
    print(f"   Error: {e}")
    print()
    print("SOLUTION: The SDK might require Windows and specific DLLs.")
    print("If you're on Linux/Mac, the .pyd file won't work.")
    print("You need to install tobii_research for your platform:")
    print("  pip install tobii-research")
    sys.exit(1)
except Exception as e:
    print(f"   ✗ Unexpected error during import!")
    print(f"   Error type: {type(e).__name__}")
    print(f"   Error: {e}")
    sys.exit(1)
print()

# 5. Check for interop module (the binary component)
print(f"5. Checking binary interop module...")
try:
    from tobiiresearch.interop import interop
    print(f"   ✓ Interop module loaded")
    print(f"   Interop location: {interop.__file__}")
except Exception as e:
    print(f"   ✗ Interop module failed to load")
    print(f"   Error: {e}")
    print()
    print("SOLUTION: The binary component (.pyd/.so) might be incompatible.")
    print("This usually means you need the correct platform-specific SDK.")
    sys.exit(1)
print()

# 6. Try finding eye trackers
print(f"6. Searching for eye trackers...")
try:
    trackers = tr.find_all_eyetrackers()
    print(f"   ✓ Search completed")
    print(f"   Found {len(trackers)} eye tracker(s)")
    
    if not trackers:
        print()
        print("   NO EYE TRACKERS FOUND!")
        print()
        print("   Possible reasons:")
        print("   - Eye tracker is not connected via USB")
        print("   - Eye tracker is not powered on")
        print("   - USB drivers are not installed")
        print("   - Another application is using the eye tracker")
        print("   - You're running on Linux (this SDK is Windows-only)")
        print()
        print("   Troubleshooting:")
        print("   1. Check USB connection and try different ports")
        print("   2. Restart the eye tracker")
        print("   3. Close any other eye tracking software (Tobii Studio, etc.)")
        print("   4. Check Windows Device Manager for Tobii devices")
    else:
        print()
        for idx, et in enumerate(trackers):
            print(f"   Eye Tracker #{idx + 1}:")
            print(f"     Model:         {et.model}")
            print(f"     Serial:        {et.serial_number}")
            print(f"     Device Name:   {et.device_name}")
            print(f"     Address:       {et.address}")
            print(f"     Firmware:      {et.firmware_version}")
            
            try:
                freqs = et.get_all_gaze_output_frequencies()
                print(f"     Frequencies:   {freqs}")
                print(f"     Current Freq:  {et.get_gaze_output_frequency()} Hz")
            except Exception as e:
                print(f"     Frequency check failed: {e}")
        
except Exception as e:
    print(f"   ✗ Eye tracker search failed!")
    print(f"   Error type: {type(e).__name__}")
    print(f"   Error: {e}")
    import traceback
    print()
    print("   Full traceback:")
    traceback.print_exc()
    sys.exit(1)

print()
print("="*70)
print("Diagnostics Complete")
print("="*70)

if trackers:
    print("✓ System is ready to run experiments!")
else:
    print("✗ No eye trackers detected - see troubleshooting above")
