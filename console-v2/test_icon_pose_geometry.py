"""Behavioral checks for contact stability and real glyph top alignment."""
import unittest
from PySide6.QtGui import QImage
from icon_pose_geometry import PoseGeometry, sprite_rect, silhouette_envelope, target_contact, icon_surface


class ContactGeometryTests(unittest.TestCase):
    def test_breathing_never_slides_off_the_support(self):
        for contact in ((.5,.68),(.32,.61),(.65,.47)):
            geometry=PoseGeometry(contact)
            baseline=None
            for pulse in (-1.,-.5,0.,.5,1.):
                x,y,w,h=sprite_rect((196,207),geometry,pulse)
                point=(x+w*contact[0],y+h*contact[1])
                if baseline is None: baseline=point
                self.assertAlmostEqual(point[0],baseline[0])
                self.assertAlmostEqual(point[1],baseline[1])

    def test_envelope_contains_each_extreme_and_intermediate(self):
        geometry=PoseGeometry((.4,.6)); bounds=(.12,.05,.93,.96)
        l,t,r,b=silhouette_envelope((196,207),bounds,geometry)
        for pulse in (-1.,-.8,0.,.3,1.):
            x,y,w,h=sprite_rect((196,207),geometry,pulse)
            self.assertGreaterEqual(x+w*bounds[0],l)
            self.assertGreaterEqual(y+h*bounds[1],t)
            self.assertLessEqual(x+w*bounds[2],r)
            self.assertLessEqual(y+h*bounds[3],b)

    def test_support_uses_alpha_top_instead_of_padded_rectangle(self):
        image=QImage(20,20,QImage.Format.Format_ARGB32);image.fill(0)
        for y in range(5,18):
            for x in range(3,17): image.setPixelColor(x,y,'#ffffff')
        surface=icon_surface((100,200,40,40),image)
        self.assertEqual(target_contact(surface,PoseGeometry((.5,.7))),(120.,210.))
        self.assertEqual(icon_surface((100,200,40,40),None),(100,200,40,40))
        image.fill(0)
        self.assertEqual(icon_surface((100,200,40,40),image),(100,200,40,40))

    def test_invalid_coordinates_rejected(self):
        for contact in ((True,.5),(float('nan'),.5),(.3,1.1)):
            with self.assertRaises(ValueError): PoseGeometry(contact)


if __name__=='__main__': unittest.main()
