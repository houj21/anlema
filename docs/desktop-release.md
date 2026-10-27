# 桌面端打包与分发

只覆盖 Windows。macOS 需要 Apple 证书 + macOS 构建机，暂不做。

## 一、给别人用的下载地址

```
https://github.com/houj21/anlema/releases/latest
```

打包、发布都是自动的：推一个 `v*` 开头的 tag，GitHub Actions 会构建并把安装包挂到 Release 上。

```powershell
# 1. 先把 desktop/package.json 里的 version 改成 1.0.3
git tag -a v1.0.3 -m "说明"
git push origin v1.0.3
```

工作流定义在 `.github/workflows/build-desktop.yml`（`windows-latest` 单平台）。

## 二、本地打包

```powershell
cd desktop
npm ci
npm run dist:win          # 产物在 desktop/release/
```

产物：

| 文件 | 大小 | 说明 |
| --- | --- | --- |
| `ZhuangLeMa-Setup-1.0.2.exe` | 87 MB | NSIS 安装包，发给用户 |
| `*.blockmap` | 0.1 MB | 增量更新用，可不给 |
| `win-unpacked/` | — | 免安装目录，调试用 |

## 三、用户安装时的提示（未签名）

没有代码签名证书，Windows 会弹 SmartScreen：

> Windows 已保护你的电脑

点 **更多信息 → 仍要运行** 即可继续。要不要彻底解决取决于预算：

| 方案 | 成本 | 效果 |
| --- | --- | --- |
| 现状（不签名） | 0 | 首次有警告，点一次就好 |
| OV 代码签名证书 | 约 1500–3000 元/年 | 无 SmartScreen 拦截 |
| EV 证书 | 约 3000–5000 元/年 | 立即获得声誉，无警告 |

签名配置（有证书后）：在 `package.json` 的 `build.win` 里加 `certificateFile`、
`certificatePassword`，并在工作流里用 secrets 注入。

## 四、版本号

`artifactName` 里的版本来自 `desktop/package.json` 的 `version`，**不跟 git tag 自动同步**。
发版时手动保持两者一致（当前：`version = 1.0.2`，tag `v1.0.2`）。

## 五、几个已经踩过的坑

1. **文件名和 `productName` 都用英文**。两处都不接受中文：
   - `productName` 决定安装目录（`%LOCALAPPDATA%\Programs\ZhuangLeMa`），
     中文会让 NSIS 默认安装目录出问题；
   - 文件名含中文时，GitHub 上传 Release 资产会把中文吃掉，
     `装了吗-Setup-1.0.0.exe` 会变成 `-Setup-1.0.0.exe`。
   中文靠这些地方保留：快捷方式名（`nsis.shortcutName`）、
   窗口标题（`electron/main.cjs` 的 `title`）、应用内 UI。
2. **别在 CI 里注入 `GH_TOKEN`**。electron-builder 会以为要自动发布，然后崩在
   `Cannot read properties of null (reading 'provider')`。发布统一交给工作流里的
   `softprops/action-gh-release`。
3. **静默安装必须带 `/D`**：
   ```powershell
   ZhuangLeMa-Setup-1.0.2.exe /S /D=C:\目标路径
   ```
   不带的 `/S` 会退出码 0 但什么都没装。双击交互安装不受影响。
4. **后端地址是构建时注入的**。`.env.production` 写的是线上 API，
   `.env.development` 是本机 `127.0.0.1:8899`。用户在设置里手动改过的地址存在
   localStorage，优先级最高。
5. **`npm run dist:win` 带了 `--publish never`**，本地重复执行不会误发版本。

## 六、已验证项（v1.0.2）

| 项目 | 结果 |
| --- | --- |
| 构建 | 通过，87 MB |
| GitHub Actions 自动构建 | 通过，Release 资产可下载 |
| 静默安装（带 `/D`） | 74 个文件落地，含卸载程序 |
| 交互安装向导 | 正常弹出，中文界面 |
| 启动 | 无崩溃，窗口标题「装了吗 · 今天你装了吗？」 |
| 联网 | 启动后主动建立 HTTPS 连接，走线上后端 |
| 卸载 | 文件清除干净 |
