"""Native manual landing on our disposable probe window, no user app mutation."""
import os,sys,json,subprocess,time,tempfile
from pathlib import Path
from native_edge_smoke import CHILD
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint
from main import PetApplication
from settings_model import SettingsStore
from window_edges import inspect_foreground
from drop_attachment import settle_drop
app=QApplication([]);app.setQuitOnLastWindowClosed(False)
proc=subprocess.Popen([sys.executable,'-u','-c',CHILD],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
controller=None
try:
 hwnd=int(proc.stdout.readline());time.sleep(.3)
 with tempfile.TemporaryDirectory() as folder:
  controller=PetApplication(app,SettingsStore(Path(folder)/'settings.ini'),enable_tray=False,create_console=False)
  controller.set_preference('quiet',True);controller.set_preference('paused',True)
  pet=controller.pet;edge=controller.edge_attachment;icons=controller.icon_sleep
  pet.show();app.processEvents();pet.animator.timer.stop();icons.watch.stop();icons.scanned_at=0
  edge.options.update(enabled=False,screens=False)
  surface=inspect_foreground(handle=hwnd);assert surface
  edge.poses.load_poses();choices=edge.choices([surface]);reports=[]
  for kind in ('top','left','right','bottom'):
   landing=next(item[0] for item in choices if item[0].kind==kind)
   pet.move(*(round(v) for v in landing.position));point=QPoint(*(round(v) for v in landing.anchor))
   assert settle_drop(pet,point),(kind,edge.error)
   assert edge.phase=='resting' and edge.kind==kind and pet.state.gait_until==0
   reports.append(dict(kind=kind,pose=edge.side,phase=edge.phase))
   edge.release()
  landing=choices[0][0];pet.move(*(round(v) for v in landing.position));assert settle_drop(pet,QPoint(*(round(v) for v in landing.anchor)))
  before=pet.pos()
  def command(value):proc.stdin.write(value+'\n');proc.stdin.flush();assert proc.stdout.readline().strip()=='ok'
  command('move');edge.tick();edge.animate();assert pet.pos()!=before
  command('minimize');edge.tick();assert not edge.active
  command('full');full=inspect_foreground(handle=hwnd);assert full and full.fullscreen
  corner=edge.choices([full])[0][0];pet.move(*(round(v) for v in corner.position));assert settle_drop(pet,QPoint(*(round(v) for v in corner.anchor)))
  assert edge.kind=='corner' and edge.phase=='resting'
  print(json.dumps(dict(native_drops=reports,move_follow=True,minimize_release=True,fullscreen_corner=True)))
finally:
 if controller:controller.cleanup();controller.pet.close()
 if proc.poll() is None:proc.stdin.write('quit\n');proc.stdin.flush()
 proc.wait(timeout=5)
 if proc.returncode:raise RuntimeError(proc.stderr.read())
