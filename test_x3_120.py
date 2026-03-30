#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_x3_120.py - Test script for Tobii X3-120 eye tracker

This script verifies the X3-120 connection and capabilities without running
the full experiment. Use this to test:
- Eye tracker detection
- Available frequencies
- Model information
- Gaze data streaming

Run before the full experiment to ensure everything is configured correctly.
"""

import sys
import os

# Add X3-120 SDK to path
sdk_path = os.path.join(os.path.dirname(__file__), "x3-120 SDK", "64")
sys.path.insert(0, sdk_path)

try:
    import tobii_research as tr
    print(f"✓ Tobii Research SDK loaded successfully")
    print(f"  SDK Version: {tr.__version__}")
except ImportError as e:
    print(f"✗ Failed to import tobii_research: {e}")
    print(f"  Make sure x3-120 SDK is in the correct location")
    sys.exit(1)

print("\n" + "="*60)
print("Searching for eye trackers...")
print("="*60)

trackers = tr.find_all_eyetrackers()

if not trackers:
    print("✗ No eye trackers found!")
    print("  - Make sure the X3-120 is connected via USB")
    print("  - Check if the device is powered on")
    print("  - Try reconnecting the device")
    sys.exit(1)

print(f"✓ Found {len(trackers)} eye tracker(s)\n")

for idx, et in enumerate(trackers):
    print(f"{'='*60}")
    print(f"Eye Tracker #{idx + 1}")
    print(f"{'='*60}")
    print(f"  Model:              {et.model}")
    print(f"  Serial Number:      {et.serial_number}")
    print(f"  Device Name:        {et.device_name}")
    print(f"  Address:            {et.address}")
    print(f"  Firmware Version:   {et.firmware_version}")
    
    print(f"\n  Available Frequencies:")
    freqs = et.get_all_gaze_output_frequencies()
    for freq in freqs:
        print(f"    - {freq} Hz")
    
    print(f"\n  Current Frequency:  {et.get_gaze_output_frequency()} Hz")
    
    print(f"\n  Capabilities:")
    caps = et.device_capabilities
    for cap in caps:
        print(f"    ✓ {cap}")
    
    # Test setting frequency to 120 Hz
    print(f"\n  Testing frequency change to 120 Hz...")
    try:
        if 120.0 in freqs:
            et.set_gaze_output_frequency(120.0)
            current = et.get_gaze_output_frequency()
            if current == 120.0:
                print(f"    ✓ Successfully set to 120 Hz")
            else:
                print(f"    ⚠ Set to 120 Hz but current is {current} Hz")
        else:
            print(f"    ⚠ 120 Hz not available, highest available: {max(freqs)} Hz")
    except Exception as e:
        print(f"    ✗ Error setting frequency: {e}")
    
    # Test gaze data streaming
    print(f"\n  Testing gaze data streaming...")
    gaze_count = [0]
    gaze_samples = []
    
    def gaze_callback(gaze_data):
        gaze_count[0] += 1
        if gaze_count[0] <= 5:  # Store first 5 samples
            gaze_samples.append(gaze_data)
    
    try:
        et.subscribe_to(tr.EYETRACKER_GAZE_DATA, gaze_callback, as_dictionary=True)
        print(f"    ✓ Subscribed to gaze data stream")
        print(f"    Collecting samples for 2 seconds...")
        
        import time
        time.sleep(2.0)
        
        et.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, gaze_callback)
        
        print(f"    ✓ Received {gaze_count[0]} gaze samples in 2 seconds")
        print(f"      Expected ~{int(et.get_gaze_output_frequency() * 2)} samples")
        
        if gaze_samples:
            print(f"\n    Sample gaze data structure:")
            sample = gaze_samples[0]
            for key in sorted(sample.keys())[:10]:  # Show first 10 keys
                print(f"      - {key}: {type(sample[key]).__name__}")
            if len(sample.keys()) > 10:
                print(f"      ... and {len(sample.keys()) - 10} more fields")
        
    except Exception as e:
        print(f"    ✗ Error during gaze streaming test: {e}")

print(f"\n{'='*60}")
print(f"Test completed!")
print(f"{'='*60}")
print(f"\n✓ X3-120 is ready for use in the experiment")
print(f"  You can now run: python experiment_code.py")
