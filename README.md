# 连板潜力七因子选股系统 v1.3

> 每工作日 15:35（北京时间）自动扫描 A 股主板，基于七因子模型评分并发布到 GitHub Pages 仪表盘。

**当前版本**：v1.3（概念板块分类 + 行业映射补全）

**在线仪表盘**：见下方「GitHub Pages 地址」（仓库转公开 + Pages 启用后生成）

---

## 快速部署（5 分钟完成）

本方案用 **GitHub Pages** 替代 Netlify，零成本、零第三方依赖、零密钥配置。

### 前置条件

- 一个 GitHub 账号
- 仓库 `seven-factor-stock-picker`（已存在）

### Step 1：把仓库改为 Public（公开）

GitHub Pages 免费版只支持公开仓库。代码公开后，策略逻辑会被外部看到，请确认你接受这一点。

1. 进入仓库 → **Settings** → 滚到最底部 **Danger Zone**
2. 找到 **Change repository visibility** → 点击 **Change visibility** → 选 **Public**
3. 按提示确认（可能需要输入仓库名）

### Step 2：启用 GitHub Pages

1. 进入仓库 → **Settings** → 左侧 **Pages**
2. **Build and deployment** → **Source** 选 **Deploy from a branch**
3. **Branch** 选 `main`，文件夹选 **/docs**
4. 点击 **Save**

> 等几分钟，GitHub 会在 `https://你的用户名.github.io/seven-factor-stock-picker/` 创建页面。
> 由于初始 `docs/index.html` 已随代码提交，首次启用后应能看到页面。

### Step 3：更新代码

把本包的文件覆盖到仓库根目录（注意 `docs/index.html` 是首次发布的初始页面），然后提交推送：

```bash
# 在仓库目录下
# 把更新包内的文件覆盖到对应位置后：
git add -A
git commit -m "chore: 从 Netlify 切换到 GitHub Pages"
git push
```

本次提交会触发 GitHub Pages 重新发布；同时下一次工作日 15:35 的 Actions 也会自动跑并更新。

### Step 4：验证

1. 在仓库 **Actions** 页面 → 找到 `七因子选股系统 - 每工作日自动扫描与发布` 工作流
2. 点击 **Run workflow** 手动触发一次
3. 等待约 2-3 分钟，确认 Action 成功（应看到提交 `auto: 扫描数据与网页 YYYY-MM-DD`）
4. 访问 `https://你的用户名.github.io/seven-factor-stock-picker/` 确认页面已更新

> 你也可以点 Actions 运行页右上角的 "Pages" 环境查看部署状态。

### Step 5（可选清理）

- **删除 Netlify Secrets**：仓库 Settings → Secrets and variables → Actions → 删除 `NETLIFY_AUTH_TOKEN` 和 `NETLIFY_SITE_ID`（已不再使用）
- **删除脚本** `scripts/netlify_deploy.py`：本包未包含该文件，但若仓库里还有请删除
- Netlify 旧站点 `seven-factor-stock-picker.netlify.app` 可在 Netlify 后台删除（额度已用尽，不影响 GitHub Pages）

---

## 项目结构

```
seven-factor-stock-picker/
├── .github/
│   └── workflows/
│       └── daily-update.yml    # GitHub Actions 工作流
├── docs/
│   └── index.html              # 每日自动生成的仪表盘页面（GitHub Pages 发布源）
├── scripts/
│   ├── seven_factor_scanner.py  # 七因子评分引擎（主程序）
│   └── generate_page.py         # HTML 生成模块（写入 docs/index.html）
├── data/
│   ├── concept_nodes_cache.json # 概念板块缓存（自动更新）
│   └── seven_factor_latest.json # 最新一次扫描结果
├── seven-factor-config.md       # 模型配置文档
├── .gitignore
└── README.md
```

---

## 七因子模型 v1.3

| 因子 | 满分 | 说明 |
|---|---|---|
| 个股辨识度 | 25 | 120日涨停次数 + 历史连板高度 + 涨幅排名 + 成交活跃 |
| 资金预热 | 20 | 量放大 + 净流入 + 涨放量 + 跌缩量 + 大单异动 |
| K线筹码 | 15 | 均线位置 + 多头排列 + 趋势动能 + 距高点距离 |
| 题材催化 | 10 | 热点排名 + 涨幅强度 + 涨停梯队 |
| 板块强度 | 10 | 排名 + 涨幅 + 涨停数 |
| 市值流动性 | 15 | 换手率健康区间 + 市值辅助 |
| 情绪环境 | 5 | 常态同分；极端冰点降权 ×0.9 |

**入池标准**：
- **重点观察**：调整后 ≥65 分 + 历史股性/趋势/量能三共振
- **预备池**：调整后 ≥60 分
- **观察池**：调整后 ≥50 分
- **淘汰**：调整后 <50 分

**筛选范围**：仅主板（排除科创板 688、创业板 300/301），排除 ST 股，流通市值 20-300 亿。

---

## 常见问题

### Q: Action 运行成功但页面没更新？
GitHub Pages 部署有 1-2 分钟延迟。检查仓库 Settings → Pages 是否已启用、Source 是否指向 `main /docs`、`docs/index.html` 是否已提交到 main 分支。

### Q: 提交步骤报权限错误？
确认 workflow 的 `permissions: contents: write` 存在（本包已配置）。仓库 Settings → Actions → General → Workflow permissions 也可改为 "Read and write permissions"。

### Q: 如何修改扫描时间？
编辑 `.github/workflows/daily-update.yml` 中的 cron 表达式。当前 `35 7 * * 1-5` 表示 UTC 07:35（北京时间 15:35），周一至周五。

### Q: 数据源是什么？
全部数据来自新浪财经公开 API，无需额外密钥。

---

## 技术说明

- **语言**：纯 Python 3（仅用标准库，无第三方依赖）
- **数据源**：新浪财经 API（全市场排名 + 日K线 + 概念板块）
- **发布**：GitHub Actions 跑评分 → 生成 `docs/index.html` → git commit 回 main → GitHub Pages 自动发布
- **定时**：GitHub Actions cron，工作日 UTC 07:35 = 北京时间 15:35
- **密钥**：无需任何第三方密钥或 Token（GitHub Pages 为仓库内建能力）

---

*数据仅供研究参考，不构成投资建议。*
