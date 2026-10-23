// Windows-only selection bridge. No user text is persisted or logged.
using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Automation;
using System.Windows.Forms;

class SelectionHelper {
    [StructLayout(LayoutKind.Sequential)] public struct Point { public int X,Y; }
    [DllImport("user32.dll")] static extern short GetAsyncKeyState(int key);
    [DllImport("user32.dll")] static extern bool GetCursorPos(out Point point);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window,out uint pid);
    [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr window,StringBuilder name,int max);
    [DllImport("user32.dll")] static extern uint GetClipboardSequenceNumber();
    [DllImport("user32.dll")] static extern uint GetDoubleClickTime();
    [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
    [StructLayout(LayoutKind.Sequential)] struct Input { public uint type; public InputData data; }
    [StructLayout(LayoutKind.Explicit)] struct InputData { [FieldOffset(0)] public MouseInput mouse; [FieldOffset(0)] public KeyInput key; }
    [StructLayout(LayoutKind.Sequential)] struct MouseInput { public int x,y;public uint mouseData,flags,time;public UIntPtr extra; }
    [StructLayout(LayoutKind.Sequential)] struct KeyInput { public ushort vk,scan;public uint flags,time;public UIntPtr extra; }
    [DllImport("user32.dll",SetLastError=true)] static extern uint SendInput(uint count,Input[] inputs,int size);
    static readonly JavaScriptSerializer Json=new JavaScriptSerializer();
    static void Emit(object value){Console.WriteLine(Json.Serialize(value));Console.Out.Flush();}
    static bool Down(int key){return (GetAsyncKeyState(key)&0x8000)!=0;}
    static bool Target(IntPtr hwnd){return hwnd!=IntPtr.Zero&&hwnd==GetForegroundWindow();}
    static string Class(IntPtr hwnd){var b=new StringBuilder(256);GetClassName(hwnd,b,256);return b.ToString();}
    static string Text(AutomationElement element,out bool password){
        password=false;
        for(int n=0;element!=null&&n<5;n++,element=TreeWalker.ControlViewWalker.GetParent(element)){
            if(element.Current.IsPassword){password=true;return null;}
            object pattern;
            if(element.TryGetCurrentPattern(TextPattern.Pattern,out pattern)){
                var ranges=((TextPattern)pattern).GetSelection();
                if(ranges.Length>0){var value=ranges[0].GetText(6001);if(!String.IsNullOrWhiteSpace(value))return value;}
            }
        }
        return null;
    }
    static void ReadUia(IntPtr hwnd,int x,int y){
        // This process can be killed independently if a target's COM provider hangs.
        bool password=false;string text=null;
        var focused=AutomationElement.FocusedElement;
        if(focused!=null){if(focused.Current.IsPassword){Emit(new {blocked=true});return;}
            uint pid;GetWindowThreadProcessId(hwnd,out pid);
            if(focused.Current.ProcessId==pid)text=Text(focused,out password);
        }
        if(password){Emit(new {blocked=true});return;}
        if(String.IsNullOrWhiteSpace(text)){
            var at=AutomationElement.FromPoint(new System.Windows.Point(x,y));
            uint pid;GetWindowThreadProcessId(hwnd,out pid);
            if(at!=null&&at.Current.ProcessId==pid)text=Text(at,out password);
        }
        Emit(new {text=Target(hwnd)?text:null,blocked=password});
    }
    static bool Terminal(IntPtr hwnd){
        string cls=Class(hwnd);
        if(cls=="ConsoleWindowClass"||cls=="CASCADIA_HOSTING_WINDOW_CLASS"||cls=="mintty"||cls=="PuTTY")return true;
        uint id;GetWindowThreadProcessId(hwnd,out id);
        try{string name=Process.GetProcessById((int)id).ProcessName.ToLowerInvariant();return name.Contains("terminal")||name=="cmd"||name=="powershell"||name=="pwsh"||name=="conemu64"||name=="wezterm-gui";}catch{return true;}
    }
    static void Copy(IntPtr hwnd){
        // Never inject Ctrl+C into terminals (it can interrupt a running command).
        if(!Target(hwnd)||Terminal(hwnd)||Down(1)||Down(16)||Down(17)||Down(18)||Down(91)||Down(92)){Emit(new {text=(string)null,skipped=true});return;}
        uint before=GetClipboardSequenceNumber();
        var backup=new DataObject();var original=Clipboard.GetDataObject();
        if(original!=null){
            foreach(var format in original.GetFormats(false)){
                var data=original.GetData(format,false);
                // Fail closed instead of overwriting formats we cannot preserve.
                if(data==null)throw new Exception("Clipboard backup unavailable");
                var stream=data as MemoryStream;if(stream!=null)data=new MemoryStream(stream.ToArray());
                backup.SetData(format,false,data);
            }
        }
        if(!Target(hwnd)||GetClipboardSequenceNumber()!=before)return;
        var keys=new Input[4];ushort[] vk={17,67,67,17};
        for(int i=0;i<4;i++){keys[i].type=1;keys[i].data.key=new KeyInput{vk=vk[i],flags=(uint)(i>=2?2:0)};}
        if(SendInput(4,keys,Marshal.SizeOf(typeof(Input)))!=4){Emit(new {text=(string)null,skipped=true});return;}
        for(int i=0;i<30&&GetClipboardSequenceNumber()==before&&Target(hwnd);i++)Thread.Sleep(15);
        uint captured=GetClipboardSequenceNumber();string text=null;bool restored=false;
        if(captured!=before&&Target(hwnd)){
            try{if(Clipboard.ContainsText())text=Clipboard.GetText();}
            finally{
                // Do not replace a newer clipboard written by the user/app.
                if(GetClipboardSequenceNumber()==captured){if(original==null)Clipboard.Clear();else Clipboard.SetDataObject(backup,true,3,30);restored=true;}
            }
        }
        Emit(new {text=text,skipped=false,restored=restored});
    }
    static void Watch(int[] exclude){
        bool previous=false;Point start=new Point(),lastRelease=new Point();IntPtr origin=IntPtr.Zero;
        long lastTime=0;
        var parent=Process.GetProcessById(exclude[0]);
        while(!parent.HasExited){
            bool down=Down(1);Point now;GetCursorPos(out now);
            if(down&&!previous){start=now;origin=GetForegroundWindow();}
            if(!down&&previous){
                long tick=DateTime.UtcNow.Ticks/TimeSpan.TicksPerMillisecond;
                bool drag=Math.Abs(now.X-start.X)+Math.Abs(now.Y-start.Y)>=8;
                bool twice=tick-lastTime<GetDoubleClickTime()&&Math.Abs(now.X-lastRelease.X)<5&&Math.Abs(now.Y-lastRelease.Y)<5;
                uint pid;GetWindowThreadProcessId(origin,out pid);
                if((drag||twice)&&Target(origin)&&Array.IndexOf(exclude,(int)pid)<0&&!Down(18)&&!Down(17)&&!Down(91))
                    Emit(new {kind="selection",hwnd=origin.ToInt64().ToString(),x=now.X,y=now.Y,pid=pid});
                lastTime=tick;lastRelease=now;
            }
            previous=down;Thread.Sleep(20);
        }
    }
    [STAThread] static void Main(string[] args){
        Console.OutputEncoding=new UTF8Encoding(false);SetProcessDPIAware();
        try{
            if(args[0]=="watch"){Watch(Array.ConvertAll(args[1].Split(','),Int32.Parse));return;}
            var hwnd=new IntPtr(Int64.Parse(args[1]));
            if(!Target(hwnd)){Emit(new {text=(string)null});return;}
            if(args[0]=="uia")ReadUia(hwnd,Int32.Parse(args[2]),Int32.Parse(args[3]));
            else if(args[0]=="copy")Copy(hwnd);
        }catch{Emit(new {text=(string)null,error="unavailable"});}
    }
}
