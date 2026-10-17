import unittest
from unittest.mock import patch
from action_player import ActionPlayer

class ActionTests(unittest.TestCase):
    def setUp(self):
        self.data={'sample':{'id':'sample','durations':[100,200,300]}}
        self.mock=patch('action_player.catalog',return_value=self.data)
        self.mock.start();self.addCleanup(self.mock.stop)
        self.player=ActionPlayer()

    def test_boundaries_and_end(self):
        self.player.play('sample',now=0)
        self.assertEqual(self.player.frame(0),0)
        self.assertEqual(self.player.frame(.15),1)
        self.assertEqual(self.player.frame(.4),2)
        self.assertIsNone(self.player.frame(.7))
        self.assertIsNone(self.player.action)

    def test_loop_and_speed(self):
        self.player.play('sample',loop=True,speed=2,now=0)
        self.assertEqual(self.player.frame(.32),0)
        self.assertEqual(self.player.frame(.4),1)

    def test_stop_and_replace(self):
        self.player.play('sample',now=0)
        self.player.play('sample',now=1)
        self.assertEqual(self.player.frame(1),0)
        self.player.stop();self.assertIsNone(self.player.frame(1))

    def test_intro_is_not_repeated(self):
        self.data['sample']['loop_start']=1
        self.player.play('sample',loop=True,now=0)
        self.assertEqual(self.player.frame(.05),0)
        self.assertEqual(self.player.frame(.601),1)
        self.assertEqual(self.player.frame(1.101),1)
        self.assertEqual(self.player.frame(.85),2)
        for t in range(601,10000,37):
            self.assertGreaterEqual(self.player.frame(t/1000),1)

    def test_reject_unsafe_arguments(self):
        for action,loop,speed in [('../bad',False,1),([],False,1),('sample','yes',1),('sample',False,float('nan')),('sample',False,3),('sample',False,True)]:
            with self.assertRaises(ValueError):self.player.play(action,loop,speed)

if __name__=='__main__':unittest.main()
