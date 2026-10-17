"""Probe only our own temporary native Qt window; never alter a user's app."""
import json,os,subprocess,sys,time
from window_edges import inspect_foreground

CHILD='''
import sys,json
from PySide6.QtWidgets import QApplication,QWidget
from PySide6.QtCore import QTimer,QEventLoop
app=QApplication([]);widget=QWidget();widget.setWindowTitle('Pet edge geometry check');widget.setGeometry(200,200,500,320);widget.show();app.processEvents()
print(int(widget.winId()),flush=True)
for line in sys.stdin:
    if line.strip()=='move':widget.setGeometry(260,250,620,350)
    elif line.strip()=='minimize':widget.showMinimized()
    elif line.strip()=='full':widget.showNormal();widget.showFullScreen()
    elif line.strip()=='quit':break
    loop=QEventLoop();QTimer.singleShot(300,loop.quit);loop.exec();print('ok',flush=True)
widget.close()
'''
def main():
    env=dict(os.environ);env.pop('QT_QPA_PLATFORM',None)
    proc=subprocess.Popen([sys.executable,'-u','-c',CHILD],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
    try:
        hwnd=int(proc.stdout.readline());time.sleep(.3)
        first=inspect_foreground(handle=hwnd);assert first and first.rect[2]>400,first
        def command(value):proc.stdin.write(value+'\n');proc.stdin.flush();assert proc.stdout.readline().strip()=='ok';time.sleep(.3)
        command('move');moved=inspect_foreground(handle=hwnd);assert moved and moved.rect!=first.rect
        command('minimize');assert inspect_foreground(handle=hwnd) is None
        command('full');full=inspect_foreground(handle=hwnd);assert full and full.fullscreen,full
        print(json.dumps(dict(initial=first.rect,moved=moved.rect,fullscreen=full.fullscreen,monitor=full.monitor)))
    finally:
        if proc.poll() is None:proc.stdin.write('quit\n');proc.stdin.flush()
        proc.wait(timeout=5)
        if proc.returncode:raise RuntimeError(proc.stderr.read())
if __name__=='__main__':main()
