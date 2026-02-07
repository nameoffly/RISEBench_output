# RISEBench 测评流程说明（Evaluation README）

本文件用于说明如何下载并解压评测资产（`data.zip`、`outputs.zip`），以及如何对 `outputs/bagel` 下的多语言结果进行评测。

## 1. 当前测评入口

- 批量脚本：`run_eval_all.sh`
- 核心评测脚本：`gpt_eval.py`

当前批量脚本默认测评语言：

- `th ko fi ru bn ja he yo sw`

并且**统一使用同一个数据文件**：

- `data/datav2_total_w_subtask.json`

## 2. 从 Hugging Face 下载 `data.zip` 和 `outputs.zip`

你当前使用的仓库是：

- `hisheep/RISEBench-outputs`（Dataset Repo）

### 2.1 方式一：`curl` 直接下载（推荐）

```bash
cd RISEBench_output

curl -L -o data.zip \
  "https://huggingface.co/datasets/hisheep/RISEBench-outputs/resolve/main/data.zip"

curl -L -o outputs.zip \
  "https://huggingface.co/datasets/hisheep/RISEBench-outputs/resolve/main/outputs.zip"
```

### 2.2 解压

```bash
cd RISEBench_output
unzip -o data.zip
unzip -o outputs.zip
```

如果你机器没有 `unzip`，可先安装（Ubuntu）：

```bash
sudo apt-get update && sudo apt-get install -y unzip
```

## 3. 解压后目录结构（期望）

```text
RISEBench_output/
├── data/
│   ├── datav2_total_w_subtask.json
│   ├── datav2_total_w_subtask_zh.json
│   ├── ...
│   ├── temporal_reasoning_images/
│   ├── causal_reasoning_images/
│   ├── spatial_reasoning_images/
│   └── logical_reasoning_images/
├── outputs/
│   └── bagel/
│       ├── th/
│       │   └── images/<category>/<index>.png
│       ├── ko/
│       ├── fi/
│       ├── ru/
│       ├── bn/
│       ├── ja/
│       ├── he/
│       ├── yo/
│       └── sw/
├── gpt_eval.py
└── run_eval_all.sh
```

## 4. 目录结构要求

每个语言目录必须是以下结构（已统一为 `images`）：

```text
outputs/bagel/<lang>/images/<category>/<index>.png
```

其中 `<category>` 例如：

- `temporal_reasoning`
- `causal_reasoning`
- `spatial_reasoning`
- `logical_reasoning`

支持图片后缀：`.png` / `.jpg` / `.jpeg`。

## 5. 环境准备

### 5.1 Python 依赖

建议使用独立环境并安装依赖：

```bash
pip install requests pandas numpy tqdm openpyxl xlsxwriter pillow
```

### 5.2 API 配置（已改为环境变量）

`gpt_eval.py` 现在从环境变量读取 API key，并支持 base URL：

```bash
export OPENAI_API_KEY="your_api_key"
export OPENAI_BASE_URL="https://api.bltcy.ai/v1"   # 可选；不设置会使用默认值
```

说明：
- 不传 `OPENAI_BASE_URL` 时，默认是 `https://api.bltcy.ai/v1`。
- 脚本内部会自动补全为 `/chat/completions` 请求地址。

## 6. 运行方式

### 6.1 先做静态检查（不发请求）

```bash
bash -n run_eval_all.sh
```

### 6.2 批量评测

```bash
./run_eval_all.sh
```

脚本会逐语言执行：

```bash
python gpt_eval.py --data data/datav2_total_w_subtask.json --input data --output outputs/bagel/<lang> --result-dir outputs/bagel/results
```

每个语言日志在：

- `outputs/bagel/results/<lang>_eval.log`

## 7. 评测产物说明

统一结果目录 `outputs/bagel/results` 会生成 3 类结果（按语言区分文件名）：

1. `outputs/bagel/results/<lang>.pkl`  
   断点缓存（按样本 index 保存 judge 结果），用于中断后续跑。

2. `outputs/bagel/results/<lang>_judge.xlsx`  
   逐样本详细评测结果（含 `judge_cons/judge_reas/judge_qua`、维度分、总分等）。

3. `outputs/bagel/results/<lang>_judge.csv`  
   汇总分数（Overall/Temporal/Causal/Spatial/Logical 及子任务统计）。

## 8. 验证是否跑通

可用以下命令快速检查结果文件是否齐全：

```bash
for lang in th ko fi ru bn ja he yo sw; do
  for f in "$lang.pkl" "${lang}_judge.xlsx" "${lang}_judge.csv"; do
    [ -f "outputs/bagel/results/$f" ] || echo "missing: outputs/bagel/results/$f"
  done
done
```

若无 `missing` 输出，通常说明主流程已完成。

## 9. 常见问题排查

1. `OPENAI_API_KEY is not set in the environment`  
   未设置 API key。请先 `export OPENAI_API_KEY=...`。

2. 读超时 / 重试失败  
   检查网络与 API 服务可用性，必要时更换 `OPENAI_BASE_URL`。

3. 提示找不到 `images` 目录  
   检查语言目录是否为 `outputs/bagel/<lang>/images/...`，而不是旧的 `bagel` 子目录。

4. 进程中断后是否重头开始？  
   不会。`gpt_eval.py` 会读取已有 `<lang>.pkl`，继续未完成样本。
