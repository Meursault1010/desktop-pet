# Yuki Live2D hybrid

The source artwork is `../图片/Yuki_Live2D_可动分层.psd`. The working PSD2Live
project and exported targets are in `yuki/`:

- `yuki/Yuki.psd2live`: editable PSD2Live project.
- `yuki/cmo3/`: Cubism 5.3-compatible CMO3/CAN3 export.
- `yuki/moc3/`: standard MOC3, texture atlas, physics and idle/blink/nod motions.
- `yuki/p2lrt/`: PSD2Live runtime model used by the desktop pet.
- `yuki/web/`: standalone browser preview of the same runtime model.

The desktop pet loads `assets/live2d/Yuki_Live2D.p2lrt` through the MIT-licensed
PSD2Live software runtime. It renders subtle breathing, gaze, blinking, head
drift and hair movement only while the standing idle is visible. Existing PNG
actions remain responsible for walking, sitting, rolling, dragging, impacts,
attachments and other expressive poses. The Electron packaging script already
includes the complete `assets` directory, including the model and native DLL.

The source art contains cutouts with conservative overlap extension; it does
not reconstruct all anatomy hidden behind the hair and clothing. The rig is
intended for small front-facing idle movement, not large head turns or
turnarounds. The closed-eye shapes are generated from the existing eye layers.
Inspect them before expanding the motion range. CMO3 was emitted for Cubism
5.3, but the existing Cubism External Edit MCP requires 5.4 Alpha for programmatic
editing; the exported model has not been round-tripped through the user's editor.

Regenerate or retune with PSD2Live 3.5.2 using the local workflow notes under
`work/yuki-layering/psd2live/` (that scratch directory is git-ignored). Keep
the PSD2Live MIT notice in `LICENSE-PSD2LIVE.txt` when distributing the native
runtime DLL.
