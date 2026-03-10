# EasyPicture 模块接口文档（当前实现）

**版本**：v1.2  
**日期**：2026-03-10

---

## 一、模块关系

```
main.py
  └── AppController
        ├── MainWindow（UI 容器）
        │     ├── Canvas（画布）
        │     ├── ToolBar（左侧工具栏）
        │     ├── CropPanel（裁剪底部面板）
        │     ├── LayerPanel（右侧图层清单）
        │     └── SpritePanel（雪碧图底部面板）
        ├── ImageModel（多图层数据模型 + 合成缓存）
        ├── ImageProcessor（图像纯函数处理）
        ├── GrabCutWorker / RealESRGANWorker（异步任务）
        └── HistoryManager（完整状态快照撤销/重做）
```

---

## 二、core/image_model.py

### `class ImageLayer`

- `name: str`
- `image: np.ndarray`（BGRA）
- `x: int`
- `y: int`
- `visible: bool`
- `source_path: str | None`

### `class ImageModel`

#### 只读属性

- `image -> np.ndarray | None`  
  返回当前可见图层合成结果（BGRA）。内部有缓存与脏标记。
- `width -> int` / `height -> int`
- `has_alpha -> bool`
- `is_dirty -> bool`
- `source_path -> str | None`
- `selection -> tuple[int, int, int, int] | None`
- `layers -> list[ImageLayer]`（底层 -> 顶层）
- `active_layer_index -> int`
- `active_layer -> ImageLayer | None`

#### 变更方法

- `set_image(img, path=None)`：以单图层初始化
- `update_image(img)`：扁平化更新为单图层（兼容旧编辑链路）
- `add_layer(img, name, source_path=None)`
- `set_active_layer(idx)`
- `move_layer_to(idx, x, y)`
- `set_layer_visible(idx, visible) -> bool`
- `reorder_layer(idx, action) -> int`（`up/down/top/bottom`）
- `reorder_layers_by_indices(order) -> bool`（底->顶旧索引顺序）
- `remove_layer(idx) -> bool`
- `clear_layers() -> bool`
- `set_selection(...)` / `clear_selection()`
- `mark_saved()`

#### 快照方法（Undo/Redo）

- `get_state_snapshot() -> dict`
- `restore_from_snapshot(snapshot)`

---

## 三、core/image_processor.py

### 文件读写

- `read_image(path) -> np.ndarray`（统一输出 BGRA）
- `write_image(img, path, quality=95)`（PNG/JPG/TIFF/BMP）
- `alpha_composite_white(img) -> np.ndarray`（BGRA -> BGR 白底）

### 基础处理

- `crop(img, x1, y1, x2, y2) -> np.ndarray`
- `rotate_90cw(img) -> np.ndarray`
- `rotate_90ccw(img) -> np.ndarray`
- `delete_selection(img, x1, y1, x2, y2) -> np.ndarray`
- `trim_to_content(img, threshold=0) -> np.ndarray`
- `resize_to_size(img, target_w, target_h, keep_aspect=True, sharpen=True, interp="lanczos") -> np.ndarray`

### 雪碧图

- `build_sprite_sheet(frames, per_row) -> (sheet, rows, cols)`  
  以可见图层帧顺序拼接 BGRA 雪碧图。

---

## 四、core/history.py

### `class HistoryManager`

- `push(state)`：保存完整状态快照（深拷贝）
- `undo() -> dict | None`
- `redo() -> dict | None`
- `can_undo` / `can_redo`
- `clear()`

> 历史栈存储的是“完整状态”，非单张像素图。

---

## 五、ui 层接口

## `ui/main_window.py`

### MainWindow Signals

- `open_triggered`
- `add_layer_triggered`
- `clear_layers_triggered`
- `export_triggered`
- `undo_triggered`
- `redo_triggered`
- `trim_triggered`
- `resize_triggered`
- `sprite_preview_triggered`
- `sprite_export_triggered`
- `sprite_per_row_changed(int)`

### MainWindow Properties

- `canvas -> Canvas`
- `toolbar -> ToolBar`
- `crop_panel -> CropPanel`
- `layer_panel -> LayerPanel`
- `sprite_panel -> SpritePanel`

---

## `ui/toolbar.py`

### `enum CanvasTool`

- `NONE`
- `SELECT`
- `CROP`
- `GRABCUT`
- `PAN`
- `LAYER_MOVE`
- `SPRITE`

### ToolBar Signals

- `tool_selected(int)`
- `crop_clicked`
- `delete_clicked`
- `grabcut_clicked`
- `rotate_cw_clicked`
- `rotate_ccw_clicked`
- `trim_clicked`
- `resize_clicked`
- `clarify_clicked`

---

## `ui/canvas.py`

### Canvas Signals

- `selection_changed(int, int, int, int)`
- `selection_cleared()`
- `delete_key_pressed()`
- `file_dropped(str)`
- `zoom_changed(float)`
- `layer_selected(int)`
- `layer_moved(int, int, int)`
- `layer_move_finished(int)`
- `layer_reorder_requested(int, str)`
- `layer_delete_requested(int)`

### Canvas Public Methods

- `set_layers(layers, canvas_w, canvas_h, active_idx)`
- `set_active_layer(idx)`
- `set_sprite_sheet(img | None)`（雪碧图显示开关）
- `set_tool(tool)`
- `zoom_fit()` / `zoom_in()` / `zoom_out()`
- `clear_selection()`
- `set_selection_from_panel(...)`

---

## `ui/crop_panel.py`

### CropPanel Signals

- `values_changed(int, int, int, int)`
- `crop_confirmed()`
- `crop_exported()`
- `crop_cancelled()`

---

## `ui/layer_panel.py`

### LayerPanel Signals

- `layer_selected(int)`
- `layer_visibility_toggled(int, bool)`
- `layer_order_changed(list[int])`

### LayerPanel Public Methods

- `set_layers(layers, active_idx)`
- `set_active_layer(active_idx)`

---

## `ui/sprite_panel.py`

### SpritePanel Signals

- `per_row_changed(int)`
- `preview_clicked()`
- `export_clicked()`
- `closed()`

### SpritePanel Public Methods

- `per_row -> int`
- `set_per_row(value)`
- `set_info(text)`

---

## `ui/dialogs.py`

- `JpegQualityDialog`
- `ResizeDialog`
- `AiClarifyDialog`
- `SpritePreviewDialog`（逐帧播放，支持间隔调整，默认 500ms）

---

## 六、controller/app_controller.py

### 核心职责

- 连接 UI 信号与 Core 处理逻辑
- 同步 Model / Canvas / LayerPanel / SpritePanel 状态
- 管理 Undo/Redo 快照
- 管理 GrabCut/ESRGAN 异步任务

### 主要接口（公开）

- `open_image()`
- `open_image_from_path(path)`
- `add_image_layer()` / `add_image_layer_from_path(path)`
- `clear_all_layers()`
- `export_image() -> bool`
- `do_crop()` / `do_crop_export()`
- `do_delete_selection()`
- `do_rotate_cw()` / `do_rotate_ccw()`
- `do_trim_to_content()`
- `do_resize_to_size()`
- `do_ai_clarify()`
- `preview_sprite_sheet()`
- `export_sprite_sheet()`
- `undo()` / `redo()`

---

## 七、状态同步规则（关键）

- 图层顺序真值源：`ImageModel.layers`（底->顶）
- 图层栏展示顺序：与模型顺序一致，拖拽后回写模型
- 画布普通模式：逐层绘制 + 活动图层高亮
- 画布雪碧图模式：`set_sprite_sheet()` 显示拼接结果
- 关闭雪碧图模式：恢复普通画布模式

---

## 八、说明

- 本文档描述的是当前代码实现（v1.2），可直接作为开发与联调参考。
- 历史文档中若与本文冲突，以本文和代码为准。
