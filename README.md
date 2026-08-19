# 连板潜力七因子选股系统 v1.3

> 每工作日 15:35（北京时间）自动扫描 A 股主板，基于七因子模型评分并部署到 Netlify 仪表盘。

**当前版本**：v1.3（概念板块分类 + 行业映射补全）

**在线仪表盘**：https://seven-factor-stock-picker.netlify.app

---

## 快速部署（5 分钟完成）

### 前置条件

- 一个 GitHub 账号
- 一个 Netlify 账号（已有站点：`seven-factor-stock-picker.netlify.app`）
- Netlify Personal Access Token（在 https://app.netlify.com/user/applications#personal-access-tokens 创建）

### Step 1：创建 GitHub 仓库

1. 打开 https://github.com/new
2. 仓库名建议填 `seven-factor-stock-picker`
3. 选择 **Private**（私有仓库，保护你的代码和数据）
4. 点击 Create repository

### Step 2：推送代码

在本地终端执行（把 `YOUR_USERNAME` 换成你的 GitHub 用户名）：

```bash
cd seven-factor-migration
git init
git add .
git commit -m "initial: 七因子选股系统 v1.3"
git branch -M main
git remote add origin git@github.com:YOUR_USERNAME/seven-factor-stock-picker.git
git push -u origin main
```

### Step 3：配置 GitHub Secrets

1. 进入你的 GitHub 仓库 → **Settings** → **Secrets and variables** → **Actions**
2. 点击 **New repository secret**，分别添加：

| Secret 名称 | 值 |
|---|---|
| `NETLIFY_AUTH_TOKEN` | 你的 Netlify Personal Access Token |
| `NETLIFY_SITE_ID` | `7075cc90-a2e5-4344-b828-275812ac451f` |

### Step 4：绑定 Netlify 自动部署（可选）

如果你希望 Netlify 也通过 GitHub 仓库关联方式部署（双保险）：

1. 登录 Netlify → 进入 `seven-factor-stock-picker` 站点
2. **Site configuration** → **Build & deploy** → **Continuous deployment**
3. 点击 **Link repository**，选择你的 GitHub 仓库
4. Build command 留空，Publish directory 留空（本项目的部署由 GitHub Actions 通过 API 直接推送 zip，不需要 Netlify CI）

> ⚠️ 注意：本项目的部署方式是 GitHub Actions 直接调用 Netlify Deploy API 上传 HTML，所以 Netlify CI 的 Build & deploy 不是必须的。Step 3 的 Secrets 配好就够了。

### Step 5：验证

1. 在 GitHub 仓库 → **Actions** 页面
2. 找到 `七因子选股系统 - 每工作日自动扫描与部署` 工作流
3. 点击 **Run workflow** 手动触发一次
4. 等待约 3-5 分钟，确认 Action 运行成功
5. 访问 https://seven-factor-stock-picker.netlify.app 确认页面已更新

---

## 项目结构

```
seven-factor-stock-picker/
├── .github/
│   └── workflows/
│       └── daily-update.yml    # GitHub Actions 工作流
├── scripts/
│   ├── seven_factor_scanner.py  # 七因子评分引擎（主程序）
│   └── netlify_deploy.py       # Netlify 部署模块
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

### Q: Action 运行失败提示 NETLIFY_AUTH_TOKEN 未设置？
确认在仓库 Settings → Secrets → Actions 中正确配置了两个 Secret，名称完全一致（区分大小写）。

### Q: 扫描器运行超时？
GitHub Actions 单次运行上限 6 小时，本系统通常 3-5 分钟完成。如果新浪 API 响应慢，可能在超时前中断。可以在 workflow 中增加 `workflow_dispatch` 手动重试。

### Q: 如何修改扫描时间？
编辑 `.github/workflows/daily-update.yml` 中的 cron 表达式。当前 `35 7 * * 1-5` 表示 UTC 07:35（北京时间 15:35），周一至周五。

### Q: Netlify Token 过期了怎么办？
重新在 Netlify 生成新的 Personal Access Token，然后更新 GitHub Secret 中的 `NETLIFY_AUTH_TOKEN`。

### Q: 数据源是什么？
全部数据来自新浪财经公开 API，无需额外密钥。

---

## 技术说明

- **语言**：纯 Python 3（仅用标准库，无第三方依赖）
- **数据源**：新浪财经 API（全市场排名 + 日K线 + 概念板块）
- **部署**：GitHub Actions → Netlify Deploy API（zip 方式）
- **定时**：GitHub Actions cron，工作日 UTC 07:35 = 北京时间 15:35

---

*数据仅供研究参考，不构成投资建议。*
