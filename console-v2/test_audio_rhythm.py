from array import array
import math
import unittest
from audio_rhythm import RhythmAnalyzer


def pcm(amplitude, rate=48000, channels=2, frequency=220):
    return array('f',(amplitude*math.sin(math.tau*frequency*i/rate)
                      for i in range(int(rate*.02)) for _ in range(channels))).tobytes()


class RhythmTests(unittest.TestCase):
    def test_silence_and_steady_tone_are_not_music_beats(self):
        for amplitude in (0,.03,.15):
            analyzer=RhythmAnalyzer()
            for i in range(350):
                result=analyzer.feed(pcm(amplitude),48000,2,i*.02)
            self.assertEqual(result['bpm'],0)
            self.assertNotEqual(result['kind'],'rhythm')
            self.assertEqual(result['kind']=='silent',amplitude==0)

    def test_regular_pulses_detect_tempo_and_silence_clears_history(self):
        for rate in (44100,48000):
            analyzer=RhythmAnalyzer()
            found=[]
            for i in range(450):
                amplitude=.16 if i%25<4 else .002
                result=analyzer.feed(pcm(amplitude,rate),rate,2,i*.02)
                if result['kind']=='rhythm':found.append(result['bpm'])
            self.assertTrue(found)
            self.assertTrue(all(abs(bpm-120)<=2 for bpm in found))
            self.assertLessEqual(len(analyzer.onsets),12)
            for i in range(100):result=analyzer.feed(pcm(0,rate),rate,2,9+i*.02)
            self.assertEqual(result['bpm'],0)
            self.assertEqual(len(analyzer.onsets),0)

    def test_impulse_is_notice_not_a_dance_and_invalid_samples_ignored(self):
        analyzer=RhythmAnalyzer()
        result=analyzer.feed(pcm(.8),48000,2,0)
        self.assertTrue(result['sudden'])
        self.assertEqual(result['bpm'],0)
        self.assertIsNone(analyzer.feed(array('f',[float('nan')]).tobytes(),48000,1,1))
        self.assertIsNone(analyzer.feed(b'',48000,2,1))
