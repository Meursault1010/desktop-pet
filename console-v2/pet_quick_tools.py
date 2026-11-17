"""Compact native views of the existing Electron tools; no duplicate persistence."""
import math
import time
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QLineEdit, QToolButton, QComboBox, QAbstractItemView)


def validate_snapshot(v):
    if not isinstance(v,dict) or set(v)-{'ready','clipboard','clipboardPaused','focus','todos','todoCount','error'}:
        raise ValueError('快捷工具状态无效')
    if type(v.get('ready')) is not bool or type(v.get('clipboardPaused')) is not bool:
        raise ValueError('快捷工具状态无效')
    clips,todos=v.get('clipboard'),v.get('todos')
    if not isinstance(clips,list) or len(clips)>10 or not isinstance(todos,list) or len(todos)>5:
        raise ValueError('快捷工具条目过多')
    for entry in clips+todos:
        if not isinstance(entry,dict) or not isinstance(entry.get('id'),str) or not 0<len(entry['id'])<=160 or not isinstance(entry.get('text'),str):
            raise ValueError('快捷工具条目无效')
        if len(entry['text'])>(240 if entry in clips else 200):
            raise ValueError('快捷工具文字过长')
    if any(not isinstance(e.get('due',''),str) or len(e.get('due',''))>40 for e in todos):
        raise ValueError('待办提醒无效')
    f=v.get('focus')
    if f is not None:
        # Any whole minute from 1 to 180 is a legal focus length: the four preset buttons are
        # only shortcuts, and rejecting everything else silently killed the desktop popup.
        if not isinstance(f,dict) or f.get('mode') not in ('focus','break') or type(f.get('duration')) is not int or not 1<=f['duration']<=180:
            raise ValueError('计时状态无效')
        for key,limit in (('remaining',10800),('completed',None)):
            if type(f.get(key)) not in (int,float) or not math.isfinite(f[key]) or f[key]<0 or (limit is not None and f[key]>limit):
                raise ValueError('计时状态无效')
        if f.get('end') is not None and (type(f['end']) not in (int,float) or not math.isfinite(f['end']) or f['end']<=0):
            raise ValueError('计时状态无效')
    if type(v.get('todoCount')) is not int or not 0<=v['todoCount']<=200 or not isinstance(v.get('error'),str) or len(v['error'])>200:
        raise ValueError('快捷工具状态无效')
    return v


class EditableClock(QLineEdit):
    commitRequested=Signal()

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.isReadOnly():
            self.setReadOnly(False)
            self.setCursor(Qt.CursorShape.IBeamCursor)
            super().mousePressEvent(event)
            QTimer.singleShot(0,self.selectAll)
            return
        super().mousePressEvent(event)

    def focusOutEvent(self,event):
        super().focusOutEvent(event)
        if not self.isReadOnly():
            self.setReadOnly(True)
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and not self.isReadOnly():
            self.commitRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class CommitLineEdit(QLineEdit):
    commitRequested=Signal()

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
            self.commitRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class QuickToolsPane(QWidget):
    request=Signal(str,object)

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind=kind
        self.state={}
        self.signature=None
        self.setObjectName('quick-tools')
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(8)
        self.caption=QLabel()
        self.caption.setObjectName('muted')
        self.caption.setWordWrap(True)
        layout.addWidget(self.caption)
        if kind in ('clipboard','todos'):
            self.items=QListWidget()
            self.items.setAccessibleName('最近十条剪贴板' if kind=='clipboard' else '未完成待办')
            self.items.setTextElideMode(Qt.TextElideMode.ElideRight)
            self.items.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.items.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            self.empty = QLabel('复制文字后显示在这里' if kind=='clipboard' else '暂无待办')
            self.empty.setObjectName('muted')
            self.empty.setWordWrap(True)
            self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.empty.setMinimumHeight(56)
            layout.addWidget(self.empty)
            layout.addWidget(self.items,1)
            if kind=='clipboard':
                self.items.itemDoubleClicked.connect(lambda item:self.request.emit('clipboard-copy',item.data(Qt.ItemDataRole.UserRole)))
                row=QHBoxLayout()
                self.copy=self.button('复制所选',lambda:self.copy_selected())
                self.pause=self.button('暂停记录',lambda:self.request.emit('clipboard-pause',not self.state.get('clipboardPaused',False)))
                row.addWidget(self.copy);row.addStretch();row.addWidget(self.pause)
                layout.addLayout(row)
                self.items.itemSelectionChanged.connect(lambda:self.copy.setEnabled(bool(self.items.currentItem())))
            else:
                self.items.itemChanged.connect(self.complete_item)
                row=QHBoxLayout()
                self.entry=QLineEdit()
                self.entry.setPlaceholderText('添加待办')
                self.entry.setMinimumWidth(0)
                self.entry.setMaxLength(200)
                self.entry.setAccessibleName('快捷添加待办')
                self.entry.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled,True)
                self.add=self.button('添加',self.add_todo)
                self.add.setObjectName('primary-action')
                row.addWidget(self.entry,1);row.addWidget(self.add)
                layout.addLayout(row)
                self.due=QComboBox()
                self.due.setAccessibleName('待办提醒时间')
                for text,minutes in [('不提醒',0),('30 分钟后提醒',30),('1 小时后提醒',60)]:self.due.addItem(text,minutes)
                layout.addWidget(self.due)
                self.entry.returnPressed.connect(self.add_todo)
        else:
            layout.addStretch()
            self.phase=QLabel('专注时间')
            self.phase.setObjectName('tool-phase')
            self.phase.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.clock=EditableClock('25:00')
            self.clock.setObjectName('timer-reading')
            self.clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.clock.setReadOnly(True)
            self.clock.setMaxLength(6)
            self.clock.setCursor(Qt.CursorShape.PointingHandCursor)
            self.clock.setAccessibleName('可编辑的专注剩余时间，可输入分钟或分:秒')
            self.clock.setToolTip('点击后输入分钟（如 30）或分:秒（如 30:00），按 Enter 应用')
            self.clock.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled,True)
            self.clock.commitRequested.connect(self.apply_focus_time)
            self.clock.editingFinished.connect(self.apply_focus_time)
            layout.addWidget(self.phase);layout.addWidget(self.clock)
            custom_row=QHBoxLayout();custom_row.addStretch()
            self.custom_minutes=CommitLineEdit()
            self.custom_minutes.setFixedWidth(66)
            self.custom_minutes.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.custom_minutes.setMaxLength(3)
            self.custom_minutes.setValidator(QIntValidator(1,180,self.custom_minutes))
            self.custom_minutes.setAccessibleName('自定义专注时长，分钟，1 到 180')
            self.custom_minutes.setPlaceholderText('分钟')
            self.custom_minutes.setToolTip('输入 1 到 180 分钟')
            self.custom_minutes.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled,True)
            self.custom_minutes.commitRequested.connect(self.apply_custom_minutes)
            self.custom_apply=self.button('应用',self.apply_custom_minutes)
            custom_row.addWidget(QLabel('自定义'))
            custom_row.addWidget(self.custom_minutes)
            custom_row.addWidget(QLabel('分钟'))
            custom_row.addWidget(self.custom_apply)
            custom_row.addStretch()
            layout.addLayout(custom_row)
            row=QHBoxLayout();row.addStretch()
            self.toggle=self.button('开始',lambda:self.request.emit('focus-toggle',None))
            self.toggle.setObjectName('primary-action')
            self.reset=self.button('重置',lambda:self.request.emit('focus-reset',None))
            row.addWidget(self.toggle);row.addWidget(self.reset);row.addStretch()
            layout.addLayout(row);layout.addStretch()
            self.timer=QTimer(self);self.timer.setInterval(1000);self.timer.timeout.connect(self.update_clock)
        self.feedback=QLabel()
        self.feedback.setObjectName('tool-feedback')
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)

    @staticmethod
    def button(text,callback):
        b=QToolButton();b.setText(text);b.setAccessibleName(text);b.setMinimumHeight(30);b.clicked.connect(callback);return b

    def copy_selected(self):
        item=self.items.currentItem()
        if item:self.request.emit('clipboard-copy',item.data(Qt.ItemDataRole.UserRole))

    def complete_item(self,item):
        if item.checkState()==Qt.CheckState.Checked:
            self.request.emit('todo-done',item.data(Qt.ItemDataRole.UserRole))

    def add_todo(self):
        text=self.entry.text().strip()
        if not text:return
        if getattr(self,'pending_add',None):return
        self.pending_add=(text,{e['id'] for e in self.state.get('todos',[])},self.state.get('todoCount',0))
        self.add.setEnabled(False)
        self.request.emit('todo-add',{'text':text,'minutes':self.due.currentData()})

    def apply_focus_time(self):
        if self.clock.isReadOnly():return
        parts=self.clock.text().strip().split(':')
        total=0
        try:
            if len(parts)==1:
                total=int(parts[0])*60
            elif len(parts)==2:
                minutes,seconds=(int(part) for part in parts)
                total=minutes*60+seconds
                if not 0<=seconds<60:total=0
            if not 60<=total<=10800:total=0
        except (ValueError,TypeError):pass
        if not total:
            self.feedback.setText('请输入 1–180 分钟，例如 30 或 30:00。')
        else:
            self.feedback.clear()
            self.request.emit('focus-set-seconds',total)
        self.clock.setModified(False)
        self.clock.setReadOnly(True)
        self.clock.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_clock()

    def apply_custom_minutes(self):
        try:minutes=int(self.custom_minutes.text().strip())
        except ValueError:minutes=0
        if not 1<=minutes<=180:
            self.feedback.setText('请输入 1 到 180 分钟。')
            return
        self.feedback.clear()
        self.custom_minutes.setModified(False)
        self.request.emit('focus-set-seconds',minutes*60)

    def refresh(self,state):
        self.state=state
        self.feedback.setText(state.get('error',''))
        ready=state.get('ready',False)
        if self.kind=='focus':
            self.caption.setText('点击时间可编辑' if ready else '正在连接工作台…')
            self.clock.setEnabled(ready);self.toggle.setEnabled(ready);self.reset.setEnabled(ready)
            if not self.custom_minutes.hasFocus() and not self.custom_minutes.isModified():
                focus=state.get('focus') or {}
                self.custom_minutes.setText(str(focus.get('duration',25)))
            self.custom_minutes.setEnabled(ready)
            self.custom_apply.setEnabled(ready)
            self.update_clock()
            return
        data=state.get('clipboard' if self.kind=='clipboard' else 'todos',[])
        if self.kind=='clipboard':
            paused=state.get('clipboardPaused',False)
            self.caption.setText(f'{len(data)} / 10 条 · '+('记录已暂停' if paused else '双击或选择后复制'))
            self.pause.setText('继续记录' if paused else '暂停记录')
        else:
            count=state.get('todoCount',0)
            pending=getattr(self,'pending_add',None)
            if pending:
                if count>pending[2] or any(e['text']==pending[0] and e['id'] not in pending[1] for e in data):
                    self.entry.clear();self.pending_add=None
                elif state.get('error'):self.pending_add=None
            self.caption.setText(f'{count} 项待办 · 最近 5 项' if ready else '正在连接工作台…')
            self.entry.setEnabled(ready and count<200);self.add.setEnabled(ready and count<200 and not getattr(self,'pending_add',None))
            self.due.setEnabled(ready)
        self.empty.setVisible(not bool(data))
        self.items.setVisible(bool(data))
        if data==self.signature and not state.get('error'):return
        self.signature=[dict(e) for e in data]
        previous=self.items.currentItem()
        selected=previous.data(Qt.ItemDataRole.UserRole) if previous else None
        scroll=self.items.verticalScrollBar().value()
        self.items.blockSignals(True);self.items.clear()
        for entry in data:
            text=' '.join(entry['text'].split())
            due=entry.get('due','')
            if due:
                from datetime import datetime
                try:text+='  · '+datetime.fromisoformat(due.replace('Z','+00:00')).astimezone().strftime('%m/%d %H:%M')
                except ValueError:pass
            item=QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole,entry['id'])
            item.setToolTip(entry['text']+('\n提醒：'+due if due else ''))
            self.items.addItem(item)
            if self.kind=='todos':
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
            if entry['id']==selected:self.items.setCurrentItem(item)
        if data and self.items.currentItem() is None:self.items.setCurrentRow(0)
        self.items.verticalScrollBar().setValue(scroll)
        self.items.blockSignals(False)
        if self.kind=='clipboard':self.copy.setEnabled(bool(data))
        if not data:self.items.setToolTip('复制文字后会显示在这里。' if self.kind=='clipboard' else '暂时没有待办，可以在下方添加。')

    def update_clock(self):
        if not self.clock.isReadOnly():return
        f=self.state.get('focus') or {}
        end=f.get('end')
        remaining=max(0,math.ceil(end/1000-time.time())) if end else f.get('remaining',1500)
        self.clock.setText(f'{int(remaining)//60:02d}:{int(remaining)%60:02d}')
        self.phase.setText('休息时间' if f.get('mode')=='break' else '专注时间')
        self.toggle.setText('暂停' if end else '继续' if remaining!=f.get('duration',25)*60 else '开始')

    def showEvent(self,event):
        super().showEvent(event)
        if hasattr(self,'timer'):self.timer.start()

    def hideEvent(self,event):
        if hasattr(self,'timer'):self.timer.stop()
        super().hideEvent(event)
