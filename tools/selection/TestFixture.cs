// Isolated, short-lived Windows test window. Never ships with Yuki.
using System;
using System.Drawing;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;
using System.Runtime.InteropServices;
class TestFixture {
 [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hwnd);
 [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd,IntPtr pid);
 [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
 [DllImport("user32.dll")] static extern bool AttachThreadInput(uint from,uint to,bool attach);
 static void Activate(Form form){var own=GetCurrentThreadId();var other=GetWindowThreadProcessId(GetForegroundWindow(),IntPtr.Zero);bool attached=other!=0&&other!=own&&AttachThreadInput(own,other,true);try{form.Activate();SetForegroundWindow(form.Handle);}finally{if(attached)AttachThreadInput(own,other,false);}}
 [STAThread] static void Main(){
  Console.OutputEncoding=new UTF8Encoding(false);
  var form=new Form{Text="Yuki selection integration test",Size=new Size(650,220),StartPosition=FormStartPosition.CenterScreen,TopMost=true};
  var input=new TextBox{Multiline=true,Text="Hello Yuki. Your download is complete.",Dock=DockStyle.Fill,Font=new Font("Segoe UI",22)};form.Controls.Add(input);
  var timer=new Timer{Interval=20000};timer.Tick+=(s,e)=>form.Close();timer.Start();
  var ready=new Timer{Interval=500};
  form.Shown+=(s,e)=>{Activate(form);ready.Start();};
  ready.Tick+=(s,e)=>{ready.Stop();Activate(form);input.Focus();input.SelectAll();var p=input.PointToScreen(new Point(40,20));Console.WriteLine(new JavaScriptSerializer().Serialize(new{hwnd=form.Handle.ToInt64().ToString(),foreground=GetForegroundWindow().ToInt64().ToString(),x=p.X,y=p.Y}));Console.Out.Flush();};
  Task.Run(()=>{Console.ReadLine();try{form.BeginInvoke(new Action(()=>form.Close()));}catch{}});
  Application.Run(form);
 }
}
