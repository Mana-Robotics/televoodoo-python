# Haptic Feedback API

## Overview

The Python server sends `HAPTIC` messages to the iOS app to trigger haptic vibrations based on robot sensor values (e.g., force feedback).

**Direction:** PC → iPhone (reverse of pose data flow)

---

## Binary Protocol

### HAPTIC Message (12 bytes)

| Offset | Field | Type | Bytes | Description |
|--------|-------|------|-------|-------------|
| 0 | magic | `char[4]` | 4 | `"TELE"` |
| 4 | msg_type | `uint8` | 1 | `7` (HAPTIC) |
| 5 | version | `uint8` | 1 | `1` |
| 6 | intensity | `float32` | 4 | 0.0 – 1.0 |
| 10 | channel | `uint8` | 1 | Reserved (always 0) |
| 11 | reserved | `uint8` | 1 | Reserved (always 0) |

**Byte order:** Little-endian

### Swift Parsing

```swift
struct HapticMessage {
    let intensity: Float  // 0.0 (off) to 1.0 (max)
    let channel: UInt8    // Reserved for future use
    
    init?(data: Data) {
        guard data.count >= 12,
              data.prefix(4) == Data("TELE".utf8),
              data[4] == 7,  // msg_type == HAPTIC
              data[5] == 1   // version == 1
        else { return nil }
        
        intensity = data.withUnsafeBytes { 
            $0.load(fromByteOffset: 6, as: Float.self) 
        }
        channel = data[10]
    }
}
```

---

## iOS Implementation

### When to Listen

Listen for HAPTIC messages on the same UDP socket used for sending POSE data, after session is established (ACK received).

### Recommended Haptic Mapping

```swift
import CoreHaptics

func triggerHaptic(intensity: Float) {
    // Clamp to valid range
    let clamped = max(0, min(1, intensity))
    
    // Option A: UIImpactFeedbackGenerator (simple)
    if clamped > 0.1 {
        let style: UIImpactFeedbackGenerator.FeedbackStyle = 
            clamped > 0.7 ? .heavy : clamped > 0.4 ? .medium : .light
        UIImpactFeedbackGenerator(style: style).impactOccurred(intensity: CGFloat(clamped))
    }
    
    // Option B: CoreHaptics (continuous, recommended)
    // Map intensity to CHHapticEvent parameters
}
```

### Update Rate

- Python sends at ~20 Hz (configurable by user)
- iOS should process immediately without queuing
- Latest value wins if updates arrive faster than haptic engine can play

---

## Example Flow

```
Python                              iOS
  |                                  |
  |  [Robot reads force: 25N]        |
  |  send_haptic(25, min=0, max=50)  |
  |                                  |
  |  -----> HAPTIC (intensity=0.5)   |
  |                                  |
  |                    [Play haptic @ 50% intensity]
```

---

## Notes

- `intensity = 0.0`: No haptic (can be used to stop continuous feedback)
- `intensity = 1.0`: Maximum haptic strength
- `channel`: Reserved for future multi-motor support, ignore for now
- Messages may arrive out of order (UDP); always use latest value
