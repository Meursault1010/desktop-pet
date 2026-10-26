using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Automation;

// Product adapter: only NetEase's exposed player controls; never global media keys.
class NetEaseMedia {
 static readonly object gate=new object();static bool published=false;
 static AutomationElement Find(AutomationElement root, string id) {
  foreach(var e in Elements(root))if(e.Cached.AutomationId==id)return e;return null;
 }
 static IEnumerable<AutomationElement> Elements(AutomationElement root) {
  var queue=new Queue<AutomationElement>();queue.Enqueue(root);int count=0;
  while(queue.Count>0&&count++<4000){var e=queue.Dequeue();yield return e;foreach(AutomationElement child in e.CachedChildren)queue.Enqueue(child);}
 }
 static InvokePattern Invoker(AutomationElement e) { object p;return e!=null&&e.Current.IsEnabled&&e.TryGetCurrentPattern(InvokePattern.Pattern,out p)?p as InvokePattern:null; }
 [STAThread] static void Main(string[] args) {
  Console.OutputEncoding=new UTF8Encoding(false);
  try { Run(args); } catch(Exception e) { Print(new {ok=false,error=e.Message});Environment.ExitCode=1; }
 }
 static void Print(object value) { lock(gate){if(published)return;published=true;Console.WriteLine(new JavaScriptSerializer().Serialize(value));} }
 static void Run(string[] args) {
  string command=args.Length>0?args[0]:"snapshot";
  if(Array.IndexOf(new[]{"snapshot","play","pause","previous","next","seek"},command)<0)throw new Exception("Unsupported command");
  Process target=null;string title="",artist="";
  foreach(var p in Process.GetProcessesByName("cloudmusic")) {
   if(p.MainWindowHandle==IntPtr.Zero)continue;
   string text=p.MainWindowTitle;int split=text.LastIndexOf(" - ",StringComparison.Ordinal);
   if(split<=0||split+3>=text.Length)continue;
   if(target!=null)throw new Exception("Multiple NetEase players are open");
   target=p;title=text.Substring(0,split);artist=text.Substring(split+3);
  }
  if(target==null){Print(new {ok=true,media=new {available=false}});return;}
  string app="netease-uia:"+target.Id+":"+target.MainWindowHandle.ToInt64();
  if(command!="snapshot"&&(args.Length<2||args[1]!=app))throw new Exception("Player changed; refresh first");
  if(command=="snapshot") {
   // Chromium accessibility can stop responding while minimized or changing pages.
   // Song detection must remain available independently of that optional provider.
   var fallback=new {ok=true,media=new {available=true,app=app,title=title,artist=artist,status="Unknown",observedAt=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),controls=new {play=false,pause=false,previous=false,next=false,seek=false}}};
   var worker=new Thread(()=>{try{Inspect(args,target,app,title,artist);}catch{Print(fallback);}});
   worker.IsBackground=true;worker.SetApartmentState(ApartmentState.MTA);worker.Start();
   if(!worker.Join(1600))Print(fallback);
   return;
  }
  Inspect(args,target,app,title,artist);
 }
 static void Inspect(string[] args,Process target,string app,string title,string artist) {
  string command=args.Length>0?args[0]:"snapshot";
  AutomationElement root=AutomationElement.FromHandle(target.MainWindowHandle);
  var cache=new CacheRequest();cache.TreeScope=TreeScope.Subtree;
  cache.Add(AutomationElement.NameProperty);cache.Add(AutomationElement.AutomationIdProperty);cache.Add(AutomationElement.ControlTypeProperty);
  root=root.GetUpdatedCache(cache);
  var play=Find(root,"btn_pc_minibar_play");string state=play==null?"Unknown":play.Cached.Name;
  AutomationElement previous=null,next=null,slider=null;RangeValuePattern range=null;double duration=0;
  foreach(AutomationElement b in Elements(root)) {
   if(b.Cached.ControlType!=ControlType.Button)continue;
   string name=b.Cached.Name;
   if(name=="pre")previous=b;if(name=="next")next=b;
   var m=Regex.Match(name,@"^(\d+):(\d{2})\s*/\s*(\d+):(\d{2})$");
   if(m.Success)duration=int.Parse(m.Groups[3].Value)*60+int.Parse(m.Groups[4].Value);
  }
  foreach(AutomationElement s in Elements(root)) {object pattern;
   if(s.Cached.ControlType!=ControlType.Slider)continue;
   if(s.TryGetCurrentPattern(RangeValuePattern.Pattern,out pattern)) {
    var r=(RangeValuePattern)pattern;
    if(duration>0&&Math.Abs(r.Current.Maximum-duration)<2&&r.Current.Minimum==0){slider=s;range=r;break;}
   }
  }
  bool playing=state=="pause",paused=state=="play";
  bool seek=range!=null&&!range.Current.IsReadOnly&&slider.Current.IsEnabled;
  if(command!="snapshot") {
   if(command=="seek") {
    if(args.Length!=5||args[3]!=title||args[4]!=artist)throw new Exception("Track changed; refresh first");
    double position;
    if(!seek||!double.TryParse(args[2],NumberStyles.Float,CultureInfo.InvariantCulture,out position)||double.IsNaN(position)||double.IsInfinity(position)||position<0||position>range.Current.Maximum)throw new Exception("Seek unavailable or outside track");
    range.SetValue(position);
   } else {
    AutomationElement button=command=="previous"?previous:command=="next"?next:play;
    if((command=="play"&&playing)||(command=="pause"&&paused)){} else {
     if((command=="play"||command=="pause")&&!playing&&!paused)throw new Exception("Playback state unavailable");
     var invoke=Invoker(button);if(invoke==null)throw new Exception("Control unavailable");invoke.Invoke();
    }
   }
   Thread.Sleep(180);Run(new[]{"snapshot"});return;
  }
  Print(new {ok=true,media=new {available=true,app=app,title=title,artist=artist,status=playing?"Playing":paused?"Paused":"Unknown",position=range==null?(double?)null:range.Current.Value,duration=duration>0?(double?)duration:null,start=0,rate=1,observedAt=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),controls=new {play=paused&&Invoker(play)!=null,pause=playing&&Invoker(play)!=null,previous=Invoker(previous)!=null,next=Invoker(next)!=null,seek=seek}}});
 }
}
