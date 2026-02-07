#!/usr/bin/env bash

set -u

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR" || exit 1

DATA_PATH="data/datav2_total_w_subtask.json"
INPUT_DIR="data"
OUTPUT_ROOT="outputs/bagel"
LANGS=("th" "ko" "fi" "ru" "bn" "ja" "he" "yo" "sw")

echo "请先设置环境变量 OPENAI_API_KEY（可选 OPENAI_BASE_URL）。"
echo "统一使用数据文件：${DATA_PATH}"
echo "开始依次评测：${LANGS[*]}"

for lang in "${LANGS[@]}"; do
  out_dir="${OUTPUT_ROOT}/${lang}"
  images_dir="${out_dir}/images"
  log_file="${out_dir}/eval.log"

  if [[ ! -d "$images_dir" ]]; then
    echo "跳过 ${lang}：未找到 ${images_dir}"
    continue
  fi
  if [[ ! -f "$DATA_PATH" ]]; then
    echo "退出：未找到数据文件 ${DATA_PATH}"
    exit 1
  fi

  echo "评测 ${lang}..."
  python gpt_eval.py \
    --data "$DATA_PATH" \
    --input "$INPUT_DIR" \
    --output "$out_dir" >"$log_file" 2>&1

  status=$?
  if [[ $status -ne 0 ]]; then
    echo "失败 ${lang}（exit=${status}），详见：${log_file}"
  else
    echo "完成 ${lang}，日志：${log_file}"
  fi
done

echo "全部评测完成。"
