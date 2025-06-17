# Honda City (Brazil) 2023 - Steering Vibration Analysis Log

**Date:** January 14, 2025  
**Vehicle:** 2023 Honda City (Brazil) with Bosch Radarless LKAS  
**Hardware:** Comma 3X  
**Issue:** Steering wheel vibration/tugging at 9-18 km/h speed range  

## Problem Description

### Symptoms
- Steering wheel vibrates/tugs (like rumble strip sensation) when vehicle reaches 9-18 km/h
- Vibration stops temporarily when driver lightly holds or counters the wheel
- Vibration resumes when driver releases steering wheel input
- Only benign `steerOverride` and `cruiseMismatch` events occur in logs during this speed range

### Root Cause Hypothesis
The stock Honda LKAS/ACAS system only provides steering assist above ~30 km/h (~19 mph). However, openpilot attempts to command steering torque below this threshold, causing:
1. EPS system rejecting torque commands below ~19 km/h
2. Openpilot commanding maximum torque repeatedly while EPS ignores commands
3. EPS suddenly accepting input when crossing speed threshold
4. This creates rapid on/off torque cycling perceived as vibration

## Analysis Performed

### Tools Created
1. **Log Analysis Tool**: `honda_city_steering_analysis.py`
   - Uses openpilot's native LogReader for proper parsing
   - Extracts steering torque, vehicle speed, cruise state data
   - Focuses on 9-18 km/h vibration range
   - Generates diagnostic plots

### Data Sources
- **Log Directory**: `/data/media/0/realdata`
- **DBC File**: `_bosch_2018.dbc` (Honda Bosch 2018 protocol)
- **Analysis Period**: 3 most recent drives with vibration range data

## Key Findings

### Drive Analysis Results

| Drive ID | Time in Range | Avg Speed | Torque Std Dev | Torque Range |
|----------|---------------|-----------|----------------|--------------|
| 00000034--9a934c052d--4 | 12.9s | 13.9 km/h | **1440.4 Nm** | 4928.0 Nm |
| 00000034--9a934c052d--3 | 23.9s | 12.8 km/h | **987.9 Nm** | 4206.0 Nm |
| 00000034--9a934c052d--2 | 47.3s | 14.4 km/h | **963.2 Nm** | 5077.0 Nm |

### Critical Observations

1. **Extreme Torque Values**: 
   - Standard deviation: 963-1440 Nm (normal should be <10 Nm)
   - Range: 4200-5000 Nm (indicates severe oscillation)
   - These values confirm rapid torque cycling/rejection

2. **Speed Correlation**:
   - Issue consistently occurs in 9-18 km/h range
   - Matches expected EPS speed threshold behavior
   - Most severe at ~14 km/h (middle of range)

3. **Temporal Pattern**:
   - Total problematic driving time: 84.1 seconds across 3 drives
   - Issue is reproducible and consistent
   - Occurs when cruise control set to 15 km/h as reported

## Technical Analysis

### EPS Behavior (from DBC)
- **Message ID 399 (STEER_STATUS)** contains EPS control status
- EPS likely has internal speed-based lockout below ~19 km/h
- `steer_control_active` field shows when EPS accepts commands
- Torque sensor vs commanded torque divergence indicates rejection

### Openpilot Behavior
- Lateral control system commands torque regardless of speed
- Current `min_steer_speed` setting in `values.py` ineffective for this case
- Controller continues attempting maximum torque when commands rejected

## Diagnostic Plots Generated

For each analyzed drive, the following plots were created:
1. **Timeline Analysis** (`analysis.png`):
   - Speed vs time with vibration range highlighted
   - Steering torque vs time showing oscillations

2. **Scatter Analysis** (`scatter.png`):
   - Steering torque vs speed correlation
   - Clear clustering in 9-18 km/h range

**Location**: `./steering_analysis/{drive_id}/`

## Recommended Solutions

### Option 1: Speed-Based Torque Limiting (Recommended)
**Implementation**: Modify Honda interface to gradually reduce torque commands below speed threshold

```python
# In honda/interface.py or carcontroller.py
def apply_steer_speed_limit(apply_steer, v_ego):
    # Honda City EPS speed threshold
    MIN_STEER_SPEED = 19 * CV.MPH_TO_MS  # ~30 km/h
    FADE_START_SPEED = 15 * CV.MPH_TO_MS  # ~24 km/h
    
    if v_ego < FADE_START_SPEED:
        # Gradually reduce torque as speed decreases
        speed_factor = max(0, v_ego / FADE_START_SPEED)
        apply_steer = apply_steer * speed_factor
    
    return apply_steer
```

### Option 2: EPS Status Monitoring
**Implementation**: Monitor EPS control active status and adapt accordingly

```python
# Monitor CAN ID 399 steer_control_active bit
# Reduce torque commands when EPS indicates rejection
if not eps_steer_control_active:
    apply_steer *= 0.5  # Reduce commanded torque
```

### Option 3: Disable Below Threshold (Conservative)
**Implementation**: Completely disable steering below speed threshold

```python
# In values.py - update min_steer_speed
HONDA_CITY = HondaBoschPlatformConfig(
    [HondaCarDocs("Honda City (Brazil only) 2023", "All", min_steer_speed=19. * CV.MPH_TO_MS)],
    # ... rest of config
)
```

## Implementation Plan

### Phase 1: Immediate Fix (Option 1)
1. Implement speed-based torque limiting in Honda controller
2. Test with gradual torque reduction below 24 km/h
3. Validate vibration elimination

### Phase 2: EPS Integration (Option 2)
1. Add EPS status monitoring from CAN ID 399
2. Implement adaptive torque limiting based on EPS acceptance
3. Create feedback loop for optimal torque timing

### Phase 3: Validation
1. Extended testing at various speeds 5-25 km/h
2. Verify no degradation of steering performance above threshold
3. Confirm elimination of vibration events

## Files Modified/Created

### Analysis Tools
- `honda_city_steering_analysis.py` - Main analysis tool
- `analyze_steering_logs.py` - Alternative parsing approach (unused)

### Generated Data
- `steering_analysis/summary.json` - Quantitative results
- `steering_analysis/{drive_id}/analysis.png` - Timeline plots
- `steering_analysis/{drive_id}/scatter.png` - Correlation plots

### Configuration Files to Modify
- `honda/values.py` - Platform configuration
- `honda/interface.py` - Speed-based limiting logic
- `honda/carcontroller.py` - Torque command modification

## Next Steps

1. **Implement Option 1** (speed-based torque limiting) as immediate fix
2. **Test thoroughly** at 5-25 km/h speed range
3. **Monitor for side effects** on normal steering operation
4. **Consider Option 2** for more sophisticated EPS integration
5. **Document final solution** for other Honda Bosch radarless vehicles

## References

- Honda City DBC: `/dbc/generator/honda/_bosch_2018.dbc`
- EPS Status Message: CAN ID 399 (STEER_STATUS)
- Log Analysis Tool: `honda_city_steering_analysis.py`
- Original Issue: Steering vibration at cruise control 15 km/h setting

---

## ✅ **FINAL IMPLEMENTATION - SOLUTION SUCCESSFUL**

### **Comprehensive Lateral Control Disable Below 25 km/h**

After iterative testing and refinement, the successful solution disables **ALL lateral control** below 25 km/h:

#### **Root Cause Confirmed:**
- **EPS rejection range**: 0-25 km/h (broader than initial 9-18 km/h analysis)
- **Stock Honda LKAS interference**: LKAS_HUD messages triggering stock system conflicts
- **Multiple conflict sources**: Torque commands, lateral control flags, and UI messages all contributing

#### **Final Implementation (`carcontroller.py`):**

**Core Logic:**
```python
# Single speed check with flag for all subsystems
if self.CP.carFingerprint == CAR.HONDA_CITY and CS.out.vEgo * 3.6 < 25:
  honda_city_low_speed = True
  self.last_torque = 0.0  # Disable steering torque
else:
  honda_city_low_speed = False
```

**Comprehensive Disables Below 25 km/h:**
1. **Steering Torque**: `self.last_torque = 0.0`
2. **CAN Torque Output**: `apply_torque = 0` (safety backstop)
3. **Lateral Control Flag**: `honda_lat_active = False`
4. **LKAS HUD Messages**: `lanesVisible=False, steer_required=0`
5. **Lane Visibility**: Prevents stock Honda LKAS activation

#### **Testing Evolution:**
| Approach | Speed Range | Result | Issue Found |
|----------|-------------|---------|-------------|
| Option 1: Speed-based limiting | 9-18 km/h | ❌ No improvement | Wrong approach entirely |
| Option 2: EPS monitoring | 9-18 km/h | ❌ Broke ACC/LKAS | Too complex, unsafe |
| Simple torque disable | 9-18 km/h | 🟡 Slight improvement | Range too narrow |
| Torque disable | 0-20 km/h | 🟡 Much better | Still some vibration |
| Torque disable | 0-25 km/h | 🟡 Even better | Occasional vibration |
| **Comprehensive disable** | **0-25 km/h** | **✅ Perfect** | **Complete solution** |

#### **Final Results:**
- ✅ **Zero vibration** at all speeds below 25 km/h
- ✅ **No stock LKAS conflicts** (HUD messages disabled)
- ✅ **Clean, maintainable code** (single flag controls all disables)
- ✅ **Normal operation** above 25 km/h threshold
- ✅ **No impact** on other Honda vehicles
- ✅ **No ACC/LKAS errors** (preserved all safety systems)

#### **Key Learnings:**
1. **EPS threshold broader than expected**: 25 km/h vs initial 19 km/h estimate
2. **Stock system interference**: Honda LKAS_HUD messages caused conflicts
3. **Comprehensive approach required**: Torque limiting alone was insufficient
4. **Empirical testing crucial**: Log analysis guided but real-world testing refined solution

#### **Files Modified:**
- `honda/carcontroller.py` - Comprehensive lateral control disable system
- `Honda_City_Steering_Vibration_Analysis_Log.md` - Complete documentation

---

**Analysis Completed**: January 14, 2025  
**Implementation Completed**: January 14, 2025  
**Analyst**: Claude (via openpilot log analysis)  
**Status**: ✅ **PROBLEM SOLVED** - Vibration eliminated, solution deployed 