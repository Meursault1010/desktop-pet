"""Conservative PNG handovers. Different silhouettes must never be dissolved."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


def compatible_silhouettes(before, after):
    if before is None or before.size() != after.size():
        return False
    # Compare a small premultiplied thumbnail: inexpensive on clip changes,
    # and sensitive to moved heads/limbs rather than transparent padding.
    images = [image.scaled(45,48,Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.SmoothTransformation).convertToFormat(
                              QImage.Format.Format_RGBA8888_Premultiplied)
              for image in (before,after)]
    a,b = (bytes(image.constBits()) for image in images)
    union = intersection = difference = samples = 0
    for i in range(0,len(a),4):
        left,right = a[i+3]>80,b[i+3]>80
        union += left or right
        intersection += left and right
        if left and right:
            difference += sum(abs(a[i+c]-b[i+c]) for c in range(3))
            samples += 3
    return bool(union and intersection/union >= .97 and samples
                and difference/(samples*255) < .035)


def handover_duration(before_pose, after_pose, before, after):
    if not before_pose or before_pose == after_pose:
        return 0.
    # Authored entry/recovery and side rolls already define the body poses.
    # Crossfading them produces extra heads, arms and transparent skirts.
    if before_pose[0] != 'idle' and before_pose[0] != 'action':
        return 0.
    if after_pose[0] not in ('idle','action'):
        return 0.
    return .055 if compatible_silhouettes(before,after) else 0.
