# -*- coding: utf-8 -*-
"""一次性数据修复：用 history.json 中的完整提示词回填 request_logs.json / error_logs.json 里被截断的提示词。

旧版后端写日志时把 prompt 截断为前 150 字符 + "..."。截断文本恰好是完整提示词的前缀，
用（前缀 + 模型 + 比例）与历史记录匹配即可高置信度找回全文。
"""
import json
import os

DATA = "data"


def load(name):
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save(name, obj):
    path = os.path.join(DATA, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def is_truncated(prompt):
    return prompt.endswith("...") and len(prompt) == 153


def build_index(history):
    """(model, aspect_ratio) -> [(full_prompt, record), ...]"""
    idx = {}
    for h in history:
        p = h.get("prompt") or ""
        if not p or is_truncated(p):
            continue
        key = (h.get("model"), h.get("aspect_ratio"))
        idx.setdefault(key, []).append(p)
    return idx


def repair(entries, index):
    fixed, missed = 0, 0
    for e in entries:
        req = e.get("request")
        if not isinstance(req, dict):
            continue
        p = req.get("prompt") or ""
        if not is_truncated(p):
            continue
        prefix = p[:-3]  # 去掉结尾 "..."
        candidates = index.get((req.get("model"), req.get("aspect_ratio")), [])
        fulls = [c for c in candidates if c.startswith(prefix)]
        if fulls:
            full = max(fulls, key=len)  # 同前缀多条时取最长（覆盖同提示词多次生成）
            req["prompt"] = full
            req["prompt_full_length"] = len(full)
            fixed += 1
        else:
            missed += 1
    return fixed, missed


def main():
    history = load("history.json")
    index = build_index(history)
    print(f"历史记录索引: {sum(len(v) for v in index.values())} 条完整提示词")

    logs = load("request_logs.json")
    fixed, missed = repair(logs, index)
    save("request_logs.json", logs)
    print(f"request_logs.json: 修复 {fixed} 条, 无法匹配 {missed} 条, 共 {len(logs)} 条")

    errs = load("error_logs.json")
    if errs:
        fixed2, missed2 = repair(errs, index)
        save("error_logs.json", errs)
        print(f"error_logs.json: 修复 {fixed2} 条, 无法匹配 {missed2} 条, 共 {len(errs)} 条")

    # 复查
    logs = load("request_logs.json")
    remain = sum(1 for e in logs if is_truncated((e.get("request") or {}).get("prompt", "")))
    print(f"剩余仍截断的日志: {remain} 条")


if __name__ == "__main__":
    main()
