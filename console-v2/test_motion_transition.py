import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtCore import QRect
from motion_transition import compatible_silhouettes,handover_duration


class TransitionTests(unittest.TestCase):
    def image(self,rect,color='#8bbcdf'):
        image=QImage(180,190,QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter=QPainter(image);painter.fillRect(rect,QColor(color));painter.end()
        return image

    def test_changed_silhouette_never_crossfades(self):
        standing=self.image(QRect(60,20,60,155))
        lying=self.image(QRect(10,130,155,40))
        self.assertFalse(compatible_silhouettes(standing,lying))
        self.assertEqual(handover_duration(('idle',),('action','roll',1),standing,lying),0)
        # Even a small moved arm creates two outlines; do not dissolve it.
        arm=self.image(QRect(65,20,60,155))
        self.assertFalse(compatible_silhouettes(standing,arm))

    def test_tiny_expression_change_allows_only_short_handover(self):
        before=self.image(QRect(60,20,60,155))
        after=before.copy();p=QPainter(after);p.fillRect(QRect(80,50,3,2),QColor('white'));p.end()
        self.assertTrue(compatible_silhouettes(before,after))
        self.assertEqual(handover_duration(('idle',),('action','blink',1),before,after),.055)
        self.assertEqual(handover_duration(('walk',1),('idle',),before,after),.055)
        self.assertEqual(handover_duration(('idle',),('flight',),before,after),0)

    def test_same_orientation_gets_only_a_short_settle(self):
        standing=self.image(QRect(60,20,60,155))
        arm=self.image(QRect(65,20,60,155))
        lying=self.image(QRect(10,130,155,40))
        self.assertFalse(compatible_silhouettes(standing,arm))
        # Walk rig and idle art, or two expressive clips, share a body axis.
        self.assertEqual(handover_duration(('walk',1),('idle',),standing,arm),.12)
        self.assertEqual(handover_duration(('walk',1),('action','curious',1),standing,arm),.18)
        self.assertEqual(handover_duration(('idle',),('action','curious',1),standing,arm),.12)
        self.assertEqual(handover_duration(('action','celebrate',1),('action','wave',1),standing,arm),.12)
        # Different orientations still cut hard; no double body is dissolved.
        self.assertEqual(handover_duration(('action','sit-neat',1),('idle',),lying,standing),0)
        self.assertEqual(handover_duration(('idle',),('action','prone-rest',1),standing,lying),0)
        # A direction flip mirrors the same drawing, so it must not fade.
        self.assertEqual(handover_duration(('walk',1),('walk',-1),standing,arm),0)

    def test_standing_entry_of_a_sit_clip_gets_a_short_settle(self):
        standing=self.image(QRect(60,20,60,155))
        arm=self.image(QRect(65,20,60,155))
        seated=self.image(QRect(45,95,90,80))
        # A ground-idle clip opens standing; the swap is upright-to-upright even
        # though the action's posture family is already 'sit'.
        self.assertEqual(handover_duration(('action','curious',1),('action','sit-relaxed',1),standing,arm),.12)
        self.assertEqual(handover_duration(('action','tea',1),('action','sit-neat',1),standing,arm),.12)
        # Handing over to a genuinely seated drawing still cuts hard.
        self.assertEqual(handover_duration(('action','curious',1),('action','sit-relaxed',1),standing,seated),0)

    def test_same_clip_does_not_restart_handover(self):
        image=self.image(QRect(60,20,60,155))
        self.assertEqual(handover_duration(('action','read',1),('action','read',1),image,image),0)
        self.assertEqual(handover_duration(None,('idle',),image,image),0)

    def test_shared_catalog_has_action_specific_recommended_timings(self):
        from action_player import catalog
        actions=catalog()
        self.assertLess(sum(actions['afraid']['durations']),sum(actions['tea']['durations']))
        self.assertLess(sum(actions['leap']['durations']),sum(actions['stretch']['durations']))
        self.assertGreater(max(actions['read'].get('keyframe_durations', actions['read']['durations'])),500)
        for action in actions.values():
            self.assertEqual(action['frames'],len(action['durations']))
            self.assertTrue(all(d>0 for d in action['durations']))
