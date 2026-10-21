# Device Testing Guide - Omron Bluetooth Devices

## Overview

This guide provides step-by-step instructions for testing AIVIN with real Omron Bluetooth medical devices.

## 🩺 Supported Devices

### Blood Pressure Monitors
- **Service UUID**: `00001810-0000-1000-8000-00805f9b34fb`
- **Characteristic UUID**: `00002a35-0000-1000-8000-00805f9b34fb`
- **Tested Models**: Omron BLEsmart series
- **Example**: BLEsmart_00000044005FBFC16EDC

### Weight Scales
- **Service UUID**: `0000181d-0000-1000-8000-00805f9b34fb`
- **Characteristic UUID**: `00002a9d-0000-1000-8000-00805f9b34fb`
- **Tested Models**: Omron HN-300T, Omron BF series

## 🔄 Device Behavior

### Important Timing Information

⚠️ **CRITICAL**: Omron devices broadcast Bluetooth data for a **limited time window** after measurement:

- **Blood Pressure Monitor**: Broadcasts for 3-5 seconds after measurement completes
- **Weight Scale**: Broadcasts for 3-5 seconds after weight stabilizes

**This means you MUST:**
1. Complete the measurement FIRST
2. THEN click "Connect to Real Device" button
3. Device will appear in pairing dialog
4. Select and pair quickly
5. Data will be retrieved automatically

## 📋 Testing Procedure

### Blood Pressure Monitor Testing

#### Step 1: Prepare the Device
```
1. Ensure device has batteries
2. Attach cuff to your upper arm
3. Sit comfortably with arm at heart level
4. Device should be OFF or in standby
```

#### Step 2: Take Measurement
```
1. Press START button on device
2. Wait for measurement to complete
3. Cuff will inflate and deflate
4. Device will beep when done
5. Results will display on device screen
6. ⏰ Device now broadcasts for 3-5 seconds!
```

#### Step 3: Retrieve Data
```
1. IMMEDIATELY click "Connect to Real BP Monitor" in web app
2. Pop-up will show: "BLEsmart_00000044..." (or similar)
3. Click on the device name
4. Click "Pair" button
5. Wait 1-2 seconds
6. ✅ Data appears in web app!
```

#### Expected Results
```
Systolic BP: 90-140 mmHg (typical)
Diastolic BP: 60-90 mmHg (typical)
Heart Rate: 40-200 bpm (valid range)

Example:
- Blood Pressure: 116/75 mmHg
- Heart Rate: 72 bpm
```

### Weight Scale Testing

#### Step 1: Prepare the Scale
```
1. Ensure scale has batteries
2. Place on flat, hard surface
3. Scale should be OFF or in standby
```

#### Step 2: Take Measurement
```
1. Remove shoes and heavy items
2. Step onto the scale
3. Stand still
4. Wait for display to stabilize
5. Scale will beep when done
6. Your weight will display
7. ⏰ Scale now broadcasts for 3-5 seconds!
```

#### Step 3: Retrieve Data
```
1. IMMEDIATELY click "Connect to Real Scale" in web app
2. Pop-up will show device name
3. Click on the device
4. Click "Pair" button
5. Wait 1-2 seconds
6. ✅ Weight appears in web app!
```

#### Expected Results
```
Weight: 40-200 kg (typical range)

Example:
- Weight: 75.5 kg
```

## 🔍 Troubleshooting

### Issue: Device Not Appearing in Pairing Dialog

**Symptoms:**
- Click "Connect" button
- Pairing dialog shows "No devices found"
- Or pairing dialog shows other devices but not your Omron

**Solutions:**
1. **Timing Issue (Most Common)**
   - You clicked too late!
   - The 3-5 second broadcast window has passed
   - **Fix**: Repeat measurement and click faster

2. **Bluetooth Not Enabled**
   - Check Windows Bluetooth settings
   - Turn Bluetooth ON
   - Try again

3. **Device Already Paired**
   - Go to Windows Settings → Bluetooth
   - Remove/Forget the Omron device
   - Try pairing again through web app

4. **Wrong Browser**
   - Web Bluetooth only works in Chrome/Edge
   - Switch to Chrome or Microsoft Edge
   - Try again

### Issue: Heart Rate Shows Weird Value (e.g., 2025 bpm)

**Status:** ✅ FIXED in latest version

**If you still see this:**
1. Clear browser cache (Ctrl+Shift+Delete)
2. Refresh page (Ctrl+F5)
3. Try measurement again

**Technical Note:** 
- This was caused by incorrect SFLOAT parsing
- Now properly parses IEEE 11073-20601 format
- Validates heart rate is within 40-200 bpm range

### Issue: Connection Times Out

**Symptoms:**
- Pairing successful
- "Listening for measurements..."
- But no data received

**Solutions:**
1. **Measurement Already Complete**
   - Device only sends data once after measurement
   - **Fix**: Take a new measurement
   
2. **Device Went to Sleep**
   - After broadcast window, device sleeps
   - **Fix**: Take a new measurement

3. **Battery Low**
   - Check device battery level
   - Replace batteries if low

### Issue: Wrong Data Values

**Symptoms:**
- Values seem incorrect
- Blood pressure too high/low
- Weight doesn't match

**Checks:**
1. **Proper Measurement Technique**
   - BP: Arm at heart level, sitting still
   - Weight: On flat surface, standing still
   
2. **Device Calibration**
   - Check if device needs calibration
   - Refer to device manual

3. **Multiple Measurements**
   - Take 2-3 measurements
   - Use average value

## 📊 Testing Checklist

### Before Testing
- [ ] Chrome or Edge browser installed and updated
- [ ] Bluetooth enabled on computer/tablet
- [ ] Omron device has fresh batteries
- [ ] Device is unpaired from Windows Bluetooth settings
- [ ] Web app is running (http://127.0.0.1:8000/)

### During Blood Pressure Test
- [ ] Sat comfortably for 5 minutes before measurement
- [ ] Arm at heart level
- [ ] Cuff properly positioned
- [ ] Measurement completed successfully
- [ ] Clicked "Connect" within 3-5 seconds
- [ ] Device appeared in pairing dialog
- [ ] Pairing successful
- [ ] Data retrieved correctly
- [ ] Values are reasonable (90-140/60-90 mmHg)
- [ ] Heart rate is reasonable (40-200 bpm)

### During Weight Test
- [ ] Scale on flat, hard surface
- [ ] Removed shoes and heavy items
- [ ] Stepped on scale
- [ ] Waited for display to stabilize
- [ ] Clicked "Connect" within 3-5 seconds
- [ ] Device appeared in pairing dialog
- [ ] Pairing successful
- [ ] Weight retrieved correctly
- [ ] Value is reasonable

### After Testing
- [ ] Data saved in dashboard
- [ ] Patient record shows measurements
- [ ] Queue ticket generated
- [ ] QR code displays correctly

## 🎯 Best Practices

### For Accurate Blood Pressure Readings

1. **Before Measurement:**
   - Rest for 5 minutes
   - Empty bladder
   - Don't smoke or drink caffeine for 30 minutes
   - Sit with back supported

2. **During Measurement:**
   - Arm at heart level
   - Feet flat on floor
   - Don't talk or move
   - Breathe normally

3. **Multiple Readings:**
   - Take 2-3 readings
   - Wait 1-2 minutes between readings
   - Use average value

### For Accurate Weight Readings

1. **Consistency:**
   - Same time of day
   - Same clothing (or minimal)
   - After using bathroom
   - Before eating

2. **Scale Placement:**
   - Hard, flat surface
   - Not on carpet
   - Same location each time

3. **Body Position:**
   - Stand still
   - Weight distributed evenly
   - Look straight ahead

## 📝 Sample Test Log

```
Date: December 3, 2024
Time: 7:28 PM
Device: BLEsmart_00000044005FBFC16EDC
Browser: Chrome 120

Test Sequence:
[7:28:37] Started BP measurement on device
[7:28:45] Measurement complete - displayed 116/75
[7:28:47] Clicked "Connect to Real BP Monitor"
[7:28:50] Device appeared in pairing dialog
[7:28:52] Paired successfully
[7:29:19] Connected to GATT Server
[7:29:20] Started listening for notifications
[7:29:21] Data received: 116/75 mmHg, HR: 72 bpm ✅
[7:29:30] Connection closed automatically

Result: SUCCESS
Notes: Data accurate, heart rate valid
```

## 🔧 Developer Debug Mode

For troubleshooting, enable console logging:

1. Open browser DevTools (F12)
2. Go to Console tab
3. Look for debug messages:

```javascript
BP Data received: {
    flags: "0x4",
    systolic: 116,
    diastolic: 75,
    map: 89,
    dataLength: 10
}

Pulse Rate: {
    raw: 72,
    exponent: 0,
    mantissa: 72,
    calculated: 72,
    final: 72
}
```

## 📞 Support

If you encounter issues not covered in this guide:

1. Check browser console for errors
2. Verify device is in Omron compatibility list
3. Try with a different Omron device
4. Test with simulation mode first
5. Contact support with:
   - Device model number
   - Browser console log
   - Screenshot of error

## ✅ Success Criteria

A successful test should show:

- ✅ Device discovery within 3-5 seconds
- ✅ Successful pairing
- ✅ Data retrieval within 2 seconds
- ✅ Systolic BP: 90-180 mmHg
- ✅ Diastolic BP: 60-120 mmHg
- ✅ Heart Rate: 40-200 bpm
- ✅ Weight: 20-300 kg
- ✅ Data saved to database
- ✅ No console errors

## 🎓 Training Recommendations

For healthcare staff training:

1. **Practice Session 1**: Simulation mode only
2. **Practice Session 2**: Real devices with guidance
3. **Practice Session 3**: Real devices independently
4. **Certification**: 5 successful measurements

Each staff member should successfully complete at least 5 measurements before using with actual patients.

---

**Version**: 1.0.0  
**Last Updated**: December 2024  
**Status**: Production Ready