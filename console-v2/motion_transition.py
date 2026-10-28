"""Conservative PNG handovers. Different silhouettes must never be dissolved."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from idle_states import motion_posture


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


def upright_metrics(image):
    """Visible character height and floor line as fractions of the canvas."""
    if image is None:
        return None
    scaled = image.scaled(90, 95, Qt.AspectRatioMode.IgnoreAspectRatio,
                          Qt.TransformationMode.SmoothTransformation).convertToFormat(
                              QImage.Format.Format_RGBA8888_Premultiplied)
    data = bytes(scaled.constBits())
    width = scaled.width()
    rows = [y for y in range(scaled.height())
            if any(data[(y*width+x)*4+3] > 80 for x in range(width))]
    if not rows:
        return None
    return (rows[-1]-rows[0])/scaled.height(), rows[-1]/scaled.height()


def pose_family(pose):
    if not pose:
        return None
    if pose[0] in ('idle', 'walk'):
        return 'stand'
    if pose[0] == 'action' and len(pose) > 1:
        return motion_posture(pose[1])
    return None


def handover_duration(before_pose, after_pose, before, after):
    if not before_pose or before_pose == after_pose:
        return 0.
    # Authored entry/recovery and side rolls already define the body poses.
    # Crossfading them produces extra heads, arms and transparent skirts.
    if before_pose[0] not in ('idle', 'action', 'walk'):
        return 0.
    if after_pose[0] not in ('idle', 'action', 'walk'):
        return 0.
    # The up walk is the only back-facing pose, with no face and a different
    # hair silhouette; blending it with any front-facing pose ghosts a second
    # body. Orientation changes cut hard, as they do for side-view flips.
    def back(pose):
        return pose[0] == 'walk' and pose[1] == 'walk-up'
    if back(before_pose) or back(after_pose):
        return 0.
    # A direction flip mirrors the same walk drawing; dissolving it would
    # briefly show two overlapping bodies.
    if before_pose[0] == after_pose[0] == 'walk':
        return 0.
    if compatible_silhouettes(before, after):
        return .055
    before_family, after_family = pose_family(before_pose), pose_family(after_pose)
    if before_family and before_family == after_family:
        # Same orientation but different drawings (walk rig vs idle art, or a
        # chain of actions): a short settle hides the swap without ghosting a
        # whole second body. Idle<->walk is the routine edge, so it settles
        # faster; handing a moving rig into an expressive action keeps the
        # longer blend. Different orientations still cut hard.
        if 'walk' in (before_pose[0], after_pose[0]) and 'action' in (before_pose[0], after_pose[0]):
            return .18
        return .12
    # A sit or prone clip opens on its own standing entry pose, so a chain
    # step from another upright action still swaps two standing drawings.
    # Orientation metadata would hide that swap behind a hard cut.
    before_upright, after_upright = upright_metrics(before), upright_metrics(after)
    if (before_upright and after_upright
            and min(before_upright[0], after_upright[0]) >= .68
            and abs(before_upright[0]-after_upright[0]) <= .05):
        return .12
    return 0.
