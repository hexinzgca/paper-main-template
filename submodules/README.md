# Pinned external repositories

初始不创建 `code/`、`experiments/` 普通文件夹，也不放占位源码。
真实仓库存在并已有可访问提交后，执行 `git submodule add` 才会创建这两个挂载点。
参见 `../docs/SUBMODULES.md`。此 README 不是子模块。

ZIP 仅携带普通文件，不包含父仓库的 Git 索引／gitlink 和独立仓库历史。
新增子模块后，请以 `git clone --recurse-submodules` 获取完整工程，而不是把源码 ZIP
当作携带固定依赖历史的完整递归克隆。
