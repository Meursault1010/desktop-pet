# Yuki workbench surface

Mode: Operate. Desktop-first Electron window; default 1180×820, minimum 880×640.

## Direction contract

THESIS: 安静、精密而有生命的蓝白银工作室。真实角色与操作内容决定层级，避免把每条信息做成同样的装饰卡片。

OWN-WORLD: 默认银雾，另有雪白与星夜；主题共享 text、panel、line、blue、deep 等语义。简洁无衬线中文、少量 Georgia 斜体诗句、稀疏星尘、细线和有限圆角。既有 Yuki 角色完整保留。

STORY: 用户先理解雪现在的状态和当前桌面时刻，接着完成显示、移角、陪伴模式等操作，再进入角色、AI、工具或设置细节。事件摘要仅讲述真实运行事件。

FIRST VIEWPORT: 窗口条、五项侧导航、页面标题与总览页签构成壳层。时间、天气、状态和角色在一条共享区域；今日事件与陪伴节奏在下层，媒体和系统信息延续垂直节奏。编辑入口就近呈现。

FORM: User-approved blue-white-silver workbench, implemented from existing study documents and screenshots; seed: none (unavailable).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Implementation evidence

Source: observatory.css, WorkbenchApp.tsx, workbenchPreferences.ts, WorkspaceBoard.tsx, WorkbenchTools.tsx, WorkbenchSettings.tsx, CharacterWorkspace.tsx, pet_menu.py. Captures: docs/验收资料/workbench-20261020. Source and finished captures take precedence over unimplemented plan details.

Motion includes page/tab entry, FLIP reordering, pointer resizing, native star reveal, quiet stars, playing media levels, and existing character micro-motion; system/user reduced-motion takes priority. Compact/wide window modes and browser <=700px navigation fallback are implemented.

No arbitrary floating docking, outfit library, Live2D, all-day activity surveillance, or persistent mutation of quiet preference during focus is claimed. Native quick chat shares the selected local/cloud endpoint and respects Chinese IME.

## Finish status

Implementation documentation and sidecar were extracted from shipped source on 2026-10-20. Independent finish review disposition is ship: the final native menu uses Georgia italic for the wordmark and a drawn send icon, with no regression observed in recaptured menu surfaces. Source and packaged Electron smoke suites each passed nine groups with no renderer errors. This verdict covers the reviewed workbench/menu direction and two requested menu corrections, not every external service. No new shipping raster was generated in this documentation pass; existing character art was reused.

