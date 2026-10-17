#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde_json::{json, Value};
use std::{collections::HashMap, io::{BufRead, BufReader, Write}, path::PathBuf, process::{Child, ChildStdin, Command, Stdio}, sync::{Arc, Mutex, atomic::{AtomicBool, AtomicU64, Ordering}}, time::Duration};
use tauri::{Emitter, Manager, menu::{Menu, MenuItem}, tray::{TrayIconBuilder, TrayIconEvent, MouseButton, MouseButtonState}};
use tokio::sync::oneshot;

#[derive(Clone)]
struct Bridge(Arc<Inner>);
struct Inner {
    stdin: Mutex<Option<ChildStdin>>,
    child: Mutex<Option<Child>>,
    pending: Mutex<HashMap<String, oneshot::Sender<Value>>>,
    last: Mutex<Value>,
    counter: AtomicU64,
    alive: AtomicBool,
    exiting: AtomicBool,
    tray_ready: AtomicBool,
}
impl Bridge {
    fn new() -> Self { Self(Arc::new(Inner { stdin: Mutex::new(None), child: Mutex::new(None), pending: Mutex::new(HashMap::new()), last: Mutex::new(json!({})), counter: AtomicU64::new(1), alive: AtomicBool::new(false), exiting: AtomicBool::new(false), tray_ready: AtomicBool::new(false) })) }
    fn root() -> Result<PathBuf, String> {
        if let Ok(p) = std::env::var("PET_PROJECT_DIR") {
            let root = PathBuf::from(p);
            if root.join("pet_backend.py").exists() { return Ok(root); }
        }
        let exe = std::env::current_exe().map_err(|e| e.to_string())?;
        for folder in exe.ancestors().skip(1) { if folder.join("pet_backend.py").exists() { return Ok(folder.to_owned()); } }
        let dev = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..");
        if dev.join("pet_backend.py").exists() { return Ok(dev); }
        Err("找不到宠物程序，请从项目中的 start.bat 启动".into())
    }
    fn start(&self, app: tauri::AppHandle) -> Result<(), String> {
        if self.0.alive.swap(true, Ordering::SeqCst) { return Ok(()); }
        let result = self.spawn(app);
        if result.is_err() { self.0.alive.store(false, Ordering::SeqCst); }
        result
    }
    fn spawn(&self, app: tauri::AppHandle) -> Result<(), String> {
        let root = Self::root()?;
        let python = std::env::var_os("PET_PYTHON").map(PathBuf::from).unwrap_or_else(|| root.join(".venv/Scripts/python.exe"));
        if !python.is_file() { return Err("未找到 Python 环境，请先运行 install.bat".into()); }
        let mut command = Command::new(python);
        command.arg("-u").arg("-B").arg(root.join("pet_backend.py")).current_dir(&root)
            .env("PYTHONIOENCODING", "utf-8").env("PET_CONTROL_PID", std::process::id().to_string()).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped());
        if let Ok(path) = std::env::var("PET_SETTINGS_FILE") { command.arg("--settings-file").arg(path); }
        #[cfg(windows)] { use std::os::windows::process::CommandExt; command.creation_flags(0x08000000); }
        let mut child = command.spawn().map_err(|e| format!("宠物启动失败：{e}"))?;
        let input = child.stdin.take().ok_or("无法建立输入通道")?;
        let output = child.stdout.take().ok_or("无法建立输出通道")?;
        let errors = child.stderr.take().ok_or("无法建立日志通道")?;
        *self.0.stdin.lock().unwrap() = Some(input);
        *self.0.child.lock().unwrap() = Some(child);
        *self.0.last.lock().unwrap() = json!({});
        let error_app = app.clone();
        std::thread::spawn(move || { for line in BufReader::new(errors).lines().map_while(Result::ok) { let _ = error_app.emit("pet-log", line); } });
        let bridge = self.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(output).lines().map_while(Result::ok) {
                if line.len() > 2_000_000 { continue; }
                if let Ok(message) = serde_json::from_str::<Value>(&line) {
                    if let Some(state) = message.get("state") { *bridge.0.last.lock().unwrap() = state.clone(); }
                    if message.get("type").and_then(Value::as_str) == Some("response") {
                        if let Some(id) = message.get("id").and_then(Value::as_str) {
                            if let Some(sender) = bridge.0.pending.lock().unwrap().remove(id) { let _ = sender.send(message.clone()); }
                        }
                    }
                    if message.get("name").and_then(Value::as_str) == Some("open_console") { show_console(&app); }
                    if message.get("name").and_then(Value::as_str) == Some("exit_app") { bridge.0.exiting.store(true, Ordering::SeqCst); app.exit(0); }
                    let _ = app.emit("pet-message", message);
                }
            }
            bridge.0.stdin.lock().unwrap().take();
            bridge.0.pending.lock().unwrap().clear();
            if let Some(mut child) = bridge.0.child.lock().unwrap().take() { let _ = child.wait(); }
            bridge.0.alive.store(false, Ordering::SeqCst);
            let _ = app.emit("pet-disconnected", "宠物已停止，可重新连接");
            if !bridge.0.exiting.load(Ordering::SeqCst) { show_console(&app); }
        });
        Ok(())
    }
    fn send(&self, message: &Value) -> Result<(), String> {
        let mut guard = self.0.stdin.lock().unwrap();
        let input = guard.as_mut().ok_or("宠物未连接，请点击重新连接")?;
        writeln!(input, "{}", message).and_then(|_| input.flush()).map_err(|e| format!("发送失败：{e}"))
    }
    async fn request(&self, name: String, payload: Value) -> Result<Value, String> {
        if !["get_state","set_preference","set_visible","toggle_visibility","toggle_pause","jump","go_home","reset_defaults","shutdown","play_action","stop_action","refresh_desktop_icons","configure_icon_sleep","start_icon_sleep","stop_icon_sleep","configure_edge_attachment","stop_edge_attachment"].contains(&name.as_str()) { return Err("不支持的操作".into()); }
        let id = self.0.counter.fetch_add(1, Ordering::SeqCst).to_string();
        let (tx, rx) = oneshot::channel();
        self.0.pending.lock().unwrap().insert(id.clone(), tx);
        if let Err(error) = self.send(&json!({"id":id,"name":name,"payload":payload})) { self.0.pending.lock().unwrap().remove(&id); return Err(error); }
        let result = tokio::time::timeout(Duration::from_secs(5), rx).await;
        self.0.pending.lock().unwrap().remove(&id);
        let value = result.map_err(|_| "宠物响应超时，请重试")?.map_err(|_| "宠物连接已断开")?;
        if value.get("ok").and_then(Value::as_bool) != Some(true) { return Err(value["error"].as_str().unwrap_or("操作失败").to_string()); }
        Ok(value)
    }
    fn stop(&self) {
        self.0.exiting.store(true, Ordering::SeqCst);
        let _ = self.send(&json!({"id":"exit","name":"shutdown"}));
        self.0.stdin.lock().unwrap().take();
        let mut guard = self.0.child.lock().unwrap();
        if let Some(child) = guard.as_mut() {
            for _ in 0..30 { if matches!(child.try_wait(), Ok(Some(_))) { return; } std::thread::sleep(Duration::from_millis(50)); }
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}
fn show_console(app: &tauri::AppHandle) { if let Some(w) = app.get_webview_window("main") { let _ = w.show(); let _ = w.unminimize(); let _ = w.set_focus(); } }
#[tauri::command]
async fn pet_command(bridge: tauri::State<'_, Bridge>, name: String, payload: Option<Value>) -> Result<Value, String> { bridge.request(name, payload.unwrap_or(json!({}))).await }
#[tauri::command]
fn restart_pet(app: tauri::AppHandle, bridge: tauri::State<'_, Bridge>) -> Result<(), String> { bridge.start(app) }
#[tauri::command]
async fn exit_app(app: tauri::AppHandle, bridge: tauri::State<'_, Bridge>) -> Result<(), String> { bridge.0.exiting.store(true, Ordering::SeqCst); let _ = bridge.request("shutdown".into(), json!({})).await; app.exit(0); Ok(()) }
fn main() {
    let bridge = Bridge::new();
    let app = tauri::Builder::default().manage(bridge.clone())
        .plugin(tauri_plugin_single_instance::init(|app, _, _| show_console(app)))
        .invoke_handler(tauri::generate_handler![pet_command, restart_pet, exit_app])
        .setup(move |app| {
            let handle = app.handle().clone();
            let open = MenuItem::with_id(app, "open", "打开控制台", true, None::<&str>)?;
            let visible = MenuItem::with_id(app, "visible", "显示 / 隐藏宠物", true, None::<&str>)?;
            let pause = MenuItem::with_id(app, "pause", "暂停 / 继续走动", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "退出小橘", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&open, &visible, &pause, &quit])?;
            let tray = TrayIconBuilder::new().icon(app.default_window_icon().unwrap().clone()).tooltip("小橘 · 桌面小屋").menu(&menu).show_menu_on_left_click(false)
                .on_tray_icon_event(|tray, event| { if matches!(event, TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. }) { show_console(tray.app_handle()); } })
                .on_menu_event(|app, event| {
                    let id = event.id.as_ref();
                    if id == "open" { show_console(app); return; }
                    let bridge = app.state::<Bridge>().inner().clone();
                    let app = app.clone();
                    let command = match id { "visible" => "toggle_visibility", "pause" => "toggle_pause", "quit" => "shutdown", _ => return };
                    if command == "shutdown" { bridge.0.exiting.store(true, Ordering::SeqCst); }
                    tauri::async_runtime::spawn(async move { let _ = bridge.request(command.into(), json!({})).await; if command == "shutdown" { app.exit(0); } });
                }).build(app);
            bridge.0.tray_ready.store(tray.is_ok(), Ordering::SeqCst);
            if let Err(error) = bridge.start(handle.clone()) { let _ = handle.emit("pet-disconnected", error); }
            if std::env::var("PET_SMOKE_TEST").is_ok() { std::thread::spawn(move || { std::thread::sleep(Duration::from_secs(4)); handle.exit(0); }); }
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let bridge = window.state::<Bridge>();
                if !bridge.0.exiting.load(Ordering::SeqCst) { api.prevent_close(); if bridge.0.tray_ready.load(Ordering::SeqCst) { let _ = window.hide(); } else { let _ = window.minimize(); } }
            }
        }).build(tauri::generate_context!()).expect("无法启动小橘控制台");
    app.run(|handle, event| { if let tauri::RunEvent::Exit = event { handle.state::<Bridge>().stop(); } });
}
